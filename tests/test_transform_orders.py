import csv
from pathlib import Path

import pytest

from src.transform_orders import StructuralValidationError, transform_orders


RAW_COLUMNS = [
    "order_id",
    "customer_id",
    "order_status",
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]


def write_orders(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RAW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def order_row(**overrides: str) -> dict[str, str]:
    row = {
        "order_id": "order-1",
        "customer_id": "customer-1",
        "order_status": "DELIVERED",
        "order_purchase_timestamp": "2017-10-02 10:56:33",
        "order_approved_at": "2017-10-02 11:07:15",
        "order_delivered_carrier_date": "2017-10-04 19:55:00",
        "order_delivered_customer_date": "2017-10-10 21:25:13",
        "order_estimated_delivery_date": "2017-10-18 00:00:00",
    }
    row.update(overrides)
    return row


def read_output(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_one_row_per_order_and_raw_row_count_preserved(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    output = tmp_path / "stg_orders.csv"
    write_orders(source, [order_row(), order_row(order_id="order-2")])

    summary = transform_orders(source, output)
    rows = read_output(output)

    assert len(rows) == 2
    assert summary.total_rows == 2
    assert summary.unique_order_ids == 2
    assert summary.duplicate_order_ids == 0


def test_required_ids_are_not_null(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    output = tmp_path / "stg_orders.csv"
    write_orders(source, [order_row(order_id="", customer_id="")])

    with pytest.raises(StructuralValidationError) as error:
        transform_orders(source, output)

    assert error.value.summary.null_order_ids == 1
    assert error.value.summary.null_customer_ids == 1
    assert not output.exists()


def test_timestamp_conversion_and_status_normalization(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    output = tmp_path / "stg_orders.csv"
    write_orders(source, [order_row()])

    transform_orders(source, output)
    row = read_output(output)[0]

    assert row["order_status"] == "delivered"
    assert row["purchased_at"] == "2017-10-02 10:56:33"
    assert row["approved_at"] == "2017-10-02 11:07:15"


def test_missing_date_flags_do_not_modify_missing_values(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    output = tmp_path / "stg_orders.csv"
    write_orders(
        source,
        [
            order_row(
                order_approved_at="",
                order_delivered_carrier_date="",
                order_delivered_customer_date="",
            )
        ],
    )

    summary = transform_orders(source, output)
    row = read_output(output)[0]

    assert row["approved_at"] == ""
    assert row["delivered_to_carrier_at"] == ""
    assert row["delivered_to_customer_at"] == ""
    assert row["missing_approval_date"] == "true"
    assert row["missing_carrier_date"] == "true"
    assert row["missing_delivery_date"] == "true"
    assert summary.missing_approval_count == 1
    assert summary.missing_carrier_date_count == 1
    assert summary.missing_customer_delivery_count == 1


def test_invalid_chronological_date_flags_preserve_values(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    output = tmp_path / "stg_orders.csv"
    write_orders(
        source,
        [
            order_row(
                order_approved_at="2017-10-02 10:00:00",
                order_delivered_carrier_date="2017-10-01 19:55:00",
                order_delivered_customer_date="2017-10-01 20:00:00",
                order_estimated_delivery_date="2017-10-01 00:00:00",
            )
        ],
    )

    summary = transform_orders(source, output)
    row = read_output(output)[0]

    assert row["approved_at"] == "2017-10-02 10:00:00"
    assert row["invalid_approval_date"] == "true"
    assert row["invalid_carrier_date"] == "true"
    assert row["invalid_delivery_date"] == "true"
    assert row["invalid_estimated_delivery_date"] == "true"
    assert summary.invalid_approval_count == 1
    assert summary.invalid_carrier_date_count == 1
    assert summary.invalid_customer_delivery_count == 1
    assert summary.invalid_estimated_delivery_count == 1


def test_late_delivery_requires_both_dates(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    output = tmp_path / "stg_orders.csv"
    write_orders(
        source,
        [
            order_row(order_id="late", order_delivered_customer_date="2017-10-20 00:00:00"),
            order_row(
                order_id="missing-estimate",
                order_estimated_delivery_date="",
                order_delivered_customer_date="2017-10-20 00:00:00",
            ),
        ],
    )

    summary = transform_orders(source, output)
    rows = {row["order_id"]: row for row in read_output(output)}

    assert rows["late"]["late_delivery"] == "true"
    assert rows["missing-estimate"]["late_delivery"] == "false"
    assert summary.late_delivery_count == 1


def test_duplicate_order_ids_are_reported_and_not_dropped(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    output = tmp_path / "stg_orders.csv"
    write_orders(source, [order_row(), order_row()])

    with pytest.raises(StructuralValidationError) as error:
        transform_orders(source, output)

    assert error.value.summary.total_rows == 2
    assert error.value.summary.duplicate_order_ids == 1
    assert not output.exists()
