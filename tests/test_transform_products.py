import csv
from pathlib import Path

import pytest

from src.transform_products import StructuralValidationError, transform_products


RAW_COLUMNS = [
    "product_id",
    "product_category_name",
    "product_name_lenght",
    "product_description_lenght",
    "product_photos_qty",
    "product_weight_g",
    "product_length_cm",
    "product_height_cm",
    "product_width_cm",
]


def product_row(**overrides: str) -> dict[str, str]:
    row = {
        "product_id": "product-1",
        "product_category_name": "perfumaria",
        "product_name_lenght": "40",
        "product_description_lenght": "287",
        "product_photos_qty": "1",
        "product_weight_g": "225",
        "product_length_cm": "16",
        "product_height_cm": "10",
        "product_width_cm": "14",
    }
    row.update(overrides)
    return row


def write_products(path: Path, rows: list[dict[str, str]], columns: list[str] | None = None) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns or RAW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def read_output(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_required_columns_are_validated(tmp_path: Path) -> None:
    source = tmp_path / "products.csv"
    write_products(source, [product_row()], columns=RAW_COLUMNS[:-1])

    with pytest.raises(ValueError, match="Unexpected products CSV columns"):
        transform_products(source, tmp_path / "stg.csv")


def test_duplicate_product_id_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "products.csv"
    write_products(source, [product_row(), product_row()])

    with pytest.raises(StructuralValidationError) as error:
        transform_products(source, tmp_path / "stg.csv")

    assert error.value.summary.duplicate_product_id_count == 1


def test_missing_product_id_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "products.csv"
    write_products(source, [product_row(product_id="")])

    with pytest.raises(StructuralValidationError) as error:
        transform_products(source, tmp_path / "stg.csv")

    assert error.value.summary.null_product_id_count == 1


def test_invalid_numeric_text_is_preserved_and_flagged(tmp_path: Path) -> None:
    source = tmp_path / "products.csv"
    output = tmp_path / "stg.csv"
    write_products(source, [product_row(product_weight_g="abc")])

    summary = transform_products(source, output)
    row = read_output(output)[0]

    assert row["product_weight_g"] == "abc"
    assert row["invalid_product_weight_g"] == "true"
    assert summary.invalid_numeric_counts["product_weight_g"] == 1


def test_missing_numeric_value_is_not_invalid(tmp_path: Path) -> None:
    source = tmp_path / "products.csv"
    output = tmp_path / "stg.csv"
    write_products(source, [product_row(product_weight_g="")])

    summary = transform_products(source, output)
    row = read_output(output)[0]

    assert row["product_weight_g"] == ""
    assert row["invalid_product_weight_g"] == "false"
    assert summary.invalid_numeric_counts["product_weight_g"] == 0


def test_output_columns_renames_lenght_and_preserves_grain(tmp_path: Path) -> None:
    source = tmp_path / "products.csv"
    output = tmp_path / "stg.csv"
    write_products(source, [product_row(), product_row(product_id="product-2")])

    transform_products(source, output)
    rows = read_output(output)

    assert list(rows[0]) == [
        "product_id",
        "product_category_name",
        "product_name_length",
        "product_description_length",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
        "missing_product_category",
        "invalid_product_name_length",
        "invalid_product_description_length",
        "invalid_product_photos_qty",
        "invalid_product_weight_g",
        "invalid_product_length_cm",
        "invalid_product_height_cm",
        "invalid_product_width_cm",
    ]
    assert len(rows) == 2
    assert len({row["product_id"] for row in rows}) == 2
    assert rows[0]["product_name_length"] == "40"
    assert rows[0]["product_description_length"] == "287"


def test_missing_category_is_preserved_and_flagged(tmp_path: Path) -> None:
    source = tmp_path / "products.csv"
    output = tmp_path / "stg.csv"
    write_products(source, [product_row(product_category_name="")])

    summary = transform_products(source, output)
    row = read_output(output)[0]

    assert row["product_category_name"] == ""
    assert row["missing_product_category"] == "true"
    assert summary.missing_category_count == 1
