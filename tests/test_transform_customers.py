import csv
from hashlib import sha256
from pathlib import Path

import pytest

from src.transform_customers import StructuralValidationError, transform_customers


RAW_COLUMNS = [
    "customer_id",
    "customer_unique_id",
    "customer_zip_code_prefix",
    "customer_city",
    "customer_state",
]


def customer_row(**overrides: str) -> dict[str, str]:
    row = {
        "customer_id": "customer-1",
        "customer_unique_id": "unique-1",
        "customer_zip_code_prefix": "01323",
        "customer_city": "sao paulo",
        "customer_state": "SP",
    }
    row.update(overrides)
    return row


def write_customers(path: Path, rows: list[dict[str, str]], columns: list[str] | None = None) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns or RAW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def read_output(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_valid_transformation_and_expected_schema(tmp_path: Path) -> None:
    source = tmp_path / "customers.csv"
    output = tmp_path / "stg.csv"
    write_customers(source, [customer_row(), customer_row(customer_id="customer-2")])

    summary = transform_customers(source, output)
    rows = read_output(output)

    assert list(rows[0]) == [
        "customer_id",
        "customer_unique_id",
        "customer_zip_code_prefix",
        "customer_city",
        "customer_state",
        "invalid_customer_zip_code_prefix",
    ]
    assert len(rows) == 2
    assert summary.total_rows == 2
    assert len({row["customer_id"] for row in rows}) == 2
    assert rows[0]["customer_zip_code_prefix"] == "01323"
    assert rows[0]["invalid_customer_zip_code_prefix"] == "false"


def test_required_columns_are_validated(tmp_path: Path) -> None:
    source = tmp_path / "customers.csv"
    write_customers(source, [customer_row()], columns=RAW_COLUMNS[:-1])

    with pytest.raises(ValueError, match="Unexpected customers CSV columns"):
        transform_customers(source, tmp_path / "stg.csv")


def test_null_customer_id_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "customers.csv"
    write_customers(source, [customer_row(customer_id="")])

    with pytest.raises(StructuralValidationError) as error:
        transform_customers(source, tmp_path / "stg.csv")

    assert error.value.summary.null_customer_id_count == 1


def test_duplicate_customer_id_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "customers.csv"
    write_customers(source, [customer_row(), customer_row()])

    with pytest.raises(StructuralValidationError) as error:
        transform_customers(source, tmp_path / "stg.csv")

    assert error.value.summary.duplicate_customer_id_count == 1


def test_customer_unique_id_duplicates_are_allowed(tmp_path: Path) -> None:
    source = tmp_path / "customers.csv"
    output = tmp_path / "stg.csv"
    write_customers(
        source,
        [
            customer_row(customer_id="customer-1", customer_unique_id="unique-1"),
            customer_row(customer_id="customer-2", customer_unique_id="unique-1"),
        ],
    )

    summary = transform_customers(source, output)

    assert summary.duplicate_customer_id_count == 0
    assert summary.unique_customer_unique_id_count == 1
    assert summary.duplicate_customer_unique_id_count == 1
    assert len(read_output(output)) == 2


def test_invalid_zip_is_flagged_and_source_text_is_preserved(tmp_path: Path) -> None:
    source = tmp_path / "customers.csv"
    output = tmp_path / "stg.csv"
    write_customers(source, [customer_row(customer_zip_code_prefix="abc")])

    summary = transform_customers(source, output)
    row = read_output(output)[0]

    assert row["customer_zip_code_prefix"] == "abc"
    assert row["invalid_customer_zip_code_prefix"] == "true"
    assert summary.invalid_customer_zip_code_prefix_count == 1


def test_raw_input_is_not_modified(tmp_path: Path) -> None:
    source = tmp_path / "customers.csv"
    output = tmp_path / "stg.csv"
    write_customers(source, [customer_row()])
    before = sha256(source.read_bytes()).hexdigest()

    transform_customers(source, output)

    assert sha256(source.read_bytes()).hexdigest() == before
