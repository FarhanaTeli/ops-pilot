import csv
from hashlib import sha256
from pathlib import Path

import pytest

from src.transform_payments import StructuralValidationError, transform_payments


RAW_COLUMNS = [
    "order_id",
    "payment_sequential",
    "payment_type",
    "payment_installments",
    "payment_value",
]


def payment_row(**overrides: str) -> dict[str, str]:
    row = {
        "order_id": "order-1",
        "payment_sequential": "1",
        "payment_type": "credit_card",
        "payment_installments": "2",
        "payment_value": "99.33",
    }
    row.update(overrides)
    return row


def write_payments(path: Path, rows: list[dict[str, str]], columns: list[str] | None = None) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns or RAW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def read_output(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_valid_transformation_preserves_schema_and_row_count(tmp_path: Path) -> None:
    source = tmp_path / "payments.csv"
    output = tmp_path / "stg.csv"
    write_payments(source, [payment_row(), payment_row(order_id="order-2")])

    summary = transform_payments(source, output)
    rows = read_output(output)

    assert list(rows[0]) == [
        "order_id",
        "payment_sequential",
        "payment_type",
        "payment_installments",
        "payment_value",
        "missing_payment_type",
        "invalid_payment_sequential",
        "invalid_payment_installments",
        "invalid_payment_value",
    ]
    assert len(rows) == 2
    assert summary.total_rows == 2
    assert summary.unique_composite_key_count == 2


def test_multiple_payments_for_one_order_are_preserved(tmp_path: Path) -> None:
    source = tmp_path / "payments.csv"
    output = tmp_path / "stg.csv"
    write_payments(
        source,
        [payment_row(payment_sequential="1"), payment_row(payment_sequential="2")],
    )

    summary = transform_payments(source, output)

    assert summary.unique_order_id_count == 1
    assert summary.unique_composite_key_count == 2
    assert len(read_output(output)) == 2


def test_duplicate_composite_key_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "payments.csv"
    write_payments(source, [payment_row(), payment_row()])

    with pytest.raises(StructuralValidationError) as error:
        transform_payments(source, tmp_path / "stg.csv")

    assert error.value.summary.duplicate_composite_key_count == 1


def test_required_columns_and_required_fields_are_validated(tmp_path: Path) -> None:
    source = tmp_path / "payments.csv"
    write_payments(source, [payment_row()], columns=RAW_COLUMNS[:-1])
    with pytest.raises(ValueError, match="Unexpected payments CSV columns"):
        transform_payments(source, tmp_path / "stg.csv")

    write_payments(source, [payment_row(order_id="", payment_sequential="")])
    with pytest.raises(StructuralValidationError) as error:
        transform_payments(source, tmp_path / "stg.csv")
    assert error.value.summary.null_order_id_count == 1
    assert error.value.summary.null_payment_sequential_count == 1


def test_invalid_numeric_values_are_preserved_and_flagged(tmp_path: Path) -> None:
    source = tmp_path / "payments.csv"
    output = tmp_path / "stg.csv"
    write_payments(
        source,
        [payment_row(payment_sequential="abc", payment_installments="bad", payment_value="oops")],
    )

    summary = transform_payments(source, output)
    row = read_output(output)[0]

    assert row["payment_sequential"] == "abc"
    assert row["payment_installments"] == "bad"
    assert row["payment_value"] == "oops"
    assert row["invalid_payment_sequential"] == "true"
    assert row["invalid_payment_installments"] == "true"
    assert row["invalid_payment_value"] == "true"
    assert summary.invalid_payment_sequential_count == 1
    assert summary.invalid_payment_installments_count == 1
    assert summary.invalid_payment_value_count == 1


def test_missing_payment_type_is_flagged(tmp_path: Path) -> None:
    source = tmp_path / "payments.csv"
    output = tmp_path / "stg.csv"
    write_payments(source, [payment_row(payment_type="")])

    summary = transform_payments(source, output)
    row = read_output(output)[0]

    assert row["payment_type"] == ""
    assert row["missing_payment_type"] == "true"
    assert summary.null_payment_type_count == 1


def test_negative_and_zero_payment_values_are_reported(tmp_path: Path) -> None:
    source = tmp_path / "payments.csv"
    output = tmp_path / "stg.csv"
    write_payments(
        source,
        [payment_row(payment_value="-1.00"), payment_row(order_id="order-2", payment_value="0.00")],
    )

    summary = transform_payments(source, output)

    assert summary.negative_payment_value_count == 1
    assert summary.zero_payment_value_count == 1


def test_raw_input_is_not_modified(tmp_path: Path) -> None:
    source = tmp_path / "payments.csv"
    output = tmp_path / "stg.csv"
    write_payments(source, [payment_row()])
    before = sha256(source.read_bytes()).hexdigest()

    transform_payments(source, output)

    assert sha256(source.read_bytes()).hexdigest() == before
