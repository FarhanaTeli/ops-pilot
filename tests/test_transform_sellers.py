import csv
from hashlib import sha256
from pathlib import Path

import pytest

from src.transform_sellers import StructuralValidationError, transform_sellers


RAW_COLUMNS = [
    "seller_id",
    "seller_zip_code_prefix",
    "seller_city",
    "seller_state",
]


def seller_row(**overrides: str) -> dict[str, str]:
    row = {
        "seller_id": "seller-1",
        "seller_zip_code_prefix": "01323",
        "seller_city": "sao paulo",
        "seller_state": "SP",
    }
    row.update(overrides)
    return row


def write_sellers(path: Path, rows: list[dict[str, str]], columns: list[str] | None = None) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns or RAW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def read_output(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_valid_transformation_preserves_schema_and_row_count(tmp_path: Path) -> None:
    source = tmp_path / "sellers.csv"
    output = tmp_path / "stg.csv"
    write_sellers(source, [seller_row(), seller_row(seller_id="seller-2")])

    summary = transform_sellers(source, output)
    rows = read_output(output)

    assert list(rows[0]) == [
        "seller_id",
        "seller_zip_code_prefix",
        "seller_city",
        "seller_state",
        "invalid_seller_zip_code_prefix",
    ]
    assert len(rows) == 2
    assert summary.total_rows == 2
    assert len({row["seller_id"] for row in rows}) == 2
    assert rows[0]["seller_zip_code_prefix"] == "01323"
    assert rows[0]["invalid_seller_zip_code_prefix"] == "false"


def test_required_columns_are_validated(tmp_path: Path) -> None:
    source = tmp_path / "sellers.csv"
    write_sellers(source, [seller_row()], columns=RAW_COLUMNS[:-1])

    with pytest.raises(ValueError, match="Unexpected sellers CSV columns"):
        transform_sellers(source, tmp_path / "stg.csv")


def test_null_seller_id_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "sellers.csv"
    write_sellers(source, [seller_row(seller_id="")])

    with pytest.raises(StructuralValidationError) as error:
        transform_sellers(source, tmp_path / "stg.csv")

    assert error.value.summary.null_seller_id_count == 1


def test_duplicate_seller_id_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "sellers.csv"
    write_sellers(source, [seller_row(), seller_row()])

    with pytest.raises(StructuralValidationError) as error:
        transform_sellers(source, tmp_path / "stg.csv")

    assert error.value.summary.duplicate_seller_id_count == 1


def test_invalid_zip_is_flagged_and_source_text_is_preserved(tmp_path: Path) -> None:
    source = tmp_path / "sellers.csv"
    output = tmp_path / "stg.csv"
    write_sellers(source, [seller_row(seller_zip_code_prefix="abc")])

    summary = transform_sellers(source, output)
    row = read_output(output)[0]

    assert row["seller_zip_code_prefix"] == "abc"
    assert row["invalid_seller_zip_code_prefix"] == "true"
    assert summary.invalid_seller_zip_code_prefix_count == 1


def test_raw_input_is_not_modified(tmp_path: Path) -> None:
    source = tmp_path / "sellers.csv"
    output = tmp_path / "stg.csv"
    write_sellers(source, [seller_row()])
    before = sha256(source.read_bytes()).hexdigest()

    transform_sellers(source, output)

    assert sha256(source.read_bytes()).hexdigest() == before
