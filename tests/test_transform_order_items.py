import csv
from pathlib import Path

import pytest

from src.transform_order_items import (
    StructuralValidationError,
    transform_order_items,
)


RAW_COLUMNS = [
    "order_id",
    "order_item_id",
    "product_id",
    "seller_id",
    "shipping_limit_date",
    "price",
    "freight_value",
]


def item_row(**overrides: str) -> dict[str, str]:
    row = {
        "order_id": "order-1",
        "order_item_id": "1",
        "product_id": "product-1",
        "seller_id": "seller-1",
        "shipping_limit_date": "2017-09-19 09:45:35",
        "price": "58.90",
        "freight_value": "13.29",
    }
    row.update(overrides)
    return row


def write_items(path: Path, rows: list[dict[str, str]], columns: list[str] | None = None) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns or RAW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def read_output(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_required_columns_are_validated(tmp_path: Path) -> None:
    source = tmp_path / "items.csv"
    write_items(source, [item_row()], columns=RAW_COLUMNS[:-1])

    with pytest.raises(ValueError, match="Unexpected order-items CSV columns"):
        transform_order_items(source, tmp_path / "stg.csv")


def test_duplicate_composite_key_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "items.csv"
    write_items(source, [item_row(), item_row()])

    with pytest.raises(StructuralValidationError) as error:
        transform_order_items(source, tmp_path / "stg.csv")

    assert error.value.summary.duplicate_composite_key_count == 1


def test_missing_mandatory_fields_are_rejected(tmp_path: Path) -> None:
    source = tmp_path / "items.csv"
    write_items(source, [item_row(order_id="", price="")])

    with pytest.raises(StructuralValidationError) as error:
        transform_order_items(source, tmp_path / "stg.csv")

    assert error.value.summary.null_order_id_count == 1
    assert error.value.summary.null_price_count == 1


def test_date_and_numeric_validation_preserve_invalid_source_values(tmp_path: Path) -> None:
    source = tmp_path / "items.csv"
    output = tmp_path / "stg.csv"
    write_items(
        source,
        [item_row(shipping_limit_date="not-a-date", price="not-a-number")],
    )

    summary = transform_order_items(source, output)
    row = read_output(output)[0]

    assert row["shipping_limit_at"] == "not-a-date"
    assert row["invalid_shipping_limit_date"] == "true"
    assert row["item_price"] == "not-a-number"
    assert row["invalid_price"] == "true"
    assert summary.invalid_date_count == 1
    assert summary.invalid_numeric_count == 1


def test_output_columns_and_row_count_preserve_item_grain(tmp_path: Path) -> None:
    source = tmp_path / "items.csv"
    output = tmp_path / "stg.csv"
    write_items(source, [item_row(), item_row(order_id="order-2")])

    transform_order_items(source, output)
    rows = read_output(output)

    assert list(rows[0]) == [
        "order_id",
        "order_item_id",
        "product_id",
        "seller_id",
        "shipping_limit_at",
        "item_price",
        "freight_value",
        "missing_shipping_limit_date",
        "invalid_shipping_limit_date",
        "invalid_price",
        "invalid_freight_value",
    ]
    assert len(rows) == 2
    assert len({(row["order_id"], row["order_item_id"]) for row in rows}) == 2
    assert rows[0]["shipping_limit_at"] == "2017-09-19 09:45:35"
    assert rows[0]["item_price"] == "58.90"


def test_missing_shipping_date_is_flagged(tmp_path: Path) -> None:
    source = tmp_path / "items.csv"
    output = tmp_path / "stg.csv"
    write_items(source, [item_row(shipping_limit_date="")])

    summary = transform_order_items(source, output)
    row = read_output(output)[0]

    assert row["shipping_limit_at"] == ""
    assert row["missing_shipping_limit_date"] == "true"
    assert row["invalid_shipping_limit_date"] == "false"
    assert summary.invalid_date_count == 0
