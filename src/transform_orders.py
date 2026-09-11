"""Transform the raw Olist orders CSV into the stg_orders dataset."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

RAW_COLUMNS = (
    "order_id",
    "customer_id",
    "order_status",
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
)

STAGING_COLUMNS = (
    "order_id",
    "customer_id",
    "order_status",
    "purchased_at",
    "approved_at",
    "delivered_to_carrier_at",
    "delivered_to_customer_at",
    "estimated_delivery_at",
    "missing_approval_date",
    "missing_carrier_date",
    "missing_delivery_date",
    "invalid_approval_date",
    "invalid_carrier_date",
    "invalid_delivery_date",
    "invalid_estimated_delivery_date",
    "late_delivery",
)

TIMESTAMP_COLUMNS = {
    "order_purchase_timestamp": "purchased_at",
    "order_approved_at": "approved_at",
    "order_delivered_carrier_date": "delivered_to_carrier_at",
    "order_delivered_customer_date": "delivered_to_customer_at",
    "order_estimated_delivery_date": "estimated_delivery_at",
}


@dataclass(frozen=True)
class ValidationSummary:
    """Counts produced while validating and transforming orders."""

    total_rows: int
    unique_order_ids: int
    duplicate_order_ids: int
    null_order_ids: int
    null_customer_ids: int
    missing_approval_count: int
    missing_carrier_date_count: int
    missing_customer_delivery_count: int
    invalid_approval_count: int
    invalid_carrier_date_count: int
    invalid_customer_delivery_count: int
    invalid_estimated_delivery_count: int
    late_delivery_count: int

    def as_dict(self) -> dict[str, int]:
        return {
            "total_rows": self.total_rows,
            "unique_order_ids": self.unique_order_ids,
            "duplicate_order_ids": self.duplicate_order_ids,
            "null_order_ids": self.null_order_ids,
            "null_customer_ids": self.null_customer_ids,
            "missing_approval_count": self.missing_approval_count,
            "missing_carrier_date_count": self.missing_carrier_date_count,
            "missing_customer_delivery_count": self.missing_customer_delivery_count,
            "invalid_approval_count": self.invalid_approval_count,
            "invalid_carrier_date_count": self.invalid_carrier_date_count,
            "invalid_customer_delivery_count": self.invalid_customer_delivery_count,
            "invalid_estimated_delivery_count": self.invalid_estimated_delivery_count,
            "late_delivery_count": self.late_delivery_count,
        }


class StructuralValidationError(ValueError):
    """Raised when the input cannot safely represent one row per order."""

    def __init__(self, message: str, summary: ValidationSummary):
        super().__init__(message)
        self.summary = summary


def _parse_timestamp(value: str | None, column: str, row_number: int) -> datetime | None:
    if value is None or value.strip() == "":
        return None
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError as error:
        raise ValueError(
            f"Invalid timestamp in column {column!r} at CSV row {row_number}: {value!r}"
        ) from error


def _format_timestamp(value: datetime | None) -> str:
    return value.isoformat(sep=" ") if value is not None else ""


def _transform_row(raw: dict[str, str], row_number: int) -> dict[str, str]:
    timestamps = {
        source: _parse_timestamp(raw.get(source), source, row_number)
        for source in TIMESTAMP_COLUMNS
    }
    purchased_at = timestamps["order_purchase_timestamp"]
    approved_at = timestamps["order_approved_at"]
    carrier_at = timestamps["order_delivered_carrier_date"]
    customer_delivery_at = timestamps["order_delivered_customer_date"]
    estimated_at = timestamps["order_estimated_delivery_date"]

    invalid_approval = bool(approved_at and purchased_at and approved_at < purchased_at)
    invalid_carrier = bool(carrier_at and purchased_at and carrier_at < purchased_at)
    invalid_delivery = bool(
        customer_delivery_at
        and purchased_at
        and (
            customer_delivery_at < purchased_at
            or (carrier_at is not None and customer_delivery_at < carrier_at)
        )
    )
    invalid_estimated = bool(estimated_at and purchased_at and estimated_at < purchased_at)
    late_delivery = bool(
        customer_delivery_at and estimated_at and customer_delivery_at > estimated_at
    )

    return {
        "order_id": raw.get("order_id", "").strip(),
        "customer_id": raw.get("customer_id", "").strip(),
        "order_status": raw.get("order_status", "").strip().lower(),
        "purchased_at": _format_timestamp(purchased_at),
        "approved_at": _format_timestamp(approved_at),
        "delivered_to_carrier_at": _format_timestamp(carrier_at),
        "delivered_to_customer_at": _format_timestamp(customer_delivery_at),
        "estimated_delivery_at": _format_timestamp(estimated_at),
        "missing_approval_date": str(approved_at is None).lower(),
        "missing_carrier_date": str(carrier_at is None).lower(),
        "missing_delivery_date": str(customer_delivery_at is None).lower(),
        "invalid_approval_date": str(invalid_approval).lower(),
        "invalid_carrier_date": str(invalid_carrier).lower(),
        "invalid_delivery_date": str(invalid_delivery).lower(),
        "invalid_estimated_delivery_date": str(invalid_estimated).lower(),
        "late_delivery": str(late_delivery).lower(),
    }


def _read_and_transform(input_path: Path) -> tuple[list[dict[str, str]], ValidationSummary]:
    transformed: list[dict[str, str]] = []
    order_ids: list[str] = []
    null_order_ids = 0
    null_customer_ids = 0

    with input_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != RAW_COLUMNS:
            raise ValueError(
                "Unexpected orders CSV columns. "
                f"Expected {list(RAW_COLUMNS)}, got {reader.fieldnames}"
            )

        for row_number, raw in enumerate(reader, start=2):
            order_id = (raw.get("order_id") or "").strip()
            customer_id = (raw.get("customer_id") or "").strip()
            null_order_ids += not bool(order_id)
            null_customer_ids += not bool(customer_id)
            order_ids.append(order_id)
            transformed.append(_transform_row(raw, row_number))

    counts = Counter(order_ids)
    duplicate_order_ids = sum(count - 1 for count in counts.values() if count > 1)
    summary = ValidationSummary(
        total_rows=len(transformed),
        unique_order_ids=len(counts),
        duplicate_order_ids=duplicate_order_ids,
        null_order_ids=null_order_ids,
        null_customer_ids=null_customer_ids,
        missing_approval_count=sum(row["missing_approval_date"] == "true" for row in transformed),
        missing_carrier_date_count=sum(row["missing_carrier_date"] == "true" for row in transformed),
        missing_customer_delivery_count=sum(row["missing_delivery_date"] == "true" for row in transformed),
        invalid_approval_count=sum(row["invalid_approval_date"] == "true" for row in transformed),
        invalid_carrier_date_count=sum(row["invalid_carrier_date"] == "true" for row in transformed),
        invalid_customer_delivery_count=sum(row["invalid_delivery_date"] == "true" for row in transformed),
        invalid_estimated_delivery_count=sum(row["invalid_estimated_delivery_date"] == "true" for row in transformed),
        late_delivery_count=sum(row["late_delivery"] == "true" for row in transformed),
    )

    structural_errors = []
    if summary.null_order_ids:
        structural_errors.append(f"null order_id values={summary.null_order_ids}")
    if summary.null_customer_ids:
        structural_errors.append(f"null customer_id values={summary.null_customer_ids}")
    if summary.duplicate_order_ids:
        structural_errors.append(f"duplicate order_id rows={summary.duplicate_order_ids}")
    if structural_errors:
        raise StructuralValidationError(
            "Orders structural validation failed: " + "; ".join(structural_errors),
            summary,
        )

    return transformed, summary


def transform_orders(input_path: str | Path, output_path: str | Path) -> ValidationSummary:
    """Transform raw orders and write stg_orders.csv without dropping rows."""
    input_file = Path(input_path)
    output_file = Path(output_path)
    transformed, summary = _read_and_transform(input_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=STAGING_COLUMNS)
        writer.writeheader()
        writer.writerows(transformed)
    return summary


def _print_summary(summary: ValidationSummary) -> None:
    print("Validation summary")
    for name, value in summary.as_dict().items():
        print(f"{name}: {value}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/raw/olist_orders_dataset.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/stg_orders.csv"),
    )
    args = parser.parse_args()
    summary = transform_orders(args.input, args.output)
    _print_summary(summary)
    print(f"Wrote: {args.output}")


if __name__ == "__main__":
    main()
