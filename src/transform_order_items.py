"""Transform raw Olist order items into the stg_order_items dataset."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

RAW_COLUMNS = (
    "order_id",
    "order_item_id",
    "product_id",
    "seller_id",
    "shipping_limit_date",
    "price",
    "freight_value",
)

STAGING_COLUMNS = (
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
)


@dataclass(frozen=True)
class ValidationSummary:
    """Counts produced while validating and transforming order items."""

    total_rows: int
    unique_order_id_count: int
    unique_composite_key_count: int
    duplicate_composite_key_count: int
    null_order_id_count: int
    null_order_item_id_count: int
    null_product_id_count: int
    null_seller_id_count: int
    null_price_count: int
    null_freight_value_count: int
    invalid_date_count: int
    invalid_numeric_count: int

    def as_dict(self) -> dict[str, int]:
        return {
            "total_rows": self.total_rows,
            "unique_order_id_count": self.unique_order_id_count,
            "unique_composite_key_count": self.unique_composite_key_count,
            "duplicate_composite_key_count": self.duplicate_composite_key_count,
            "null_order_id_count": self.null_order_id_count,
            "null_order_item_id_count": self.null_order_item_id_count,
            "null_product_id_count": self.null_product_id_count,
            "null_seller_id_count": self.null_seller_id_count,
            "null_price_count": self.null_price_count,
            "null_freight_value_count": self.null_freight_value_count,
            "invalid_date_count": self.invalid_date_count,
            "invalid_numeric_count": self.invalid_numeric_count,
        }


class StructuralValidationError(ValueError):
    """Raised when the input cannot safely represent one row per order item."""

    def __init__(self, message: str, summary: ValidationSummary):
        super().__init__(message)
        self.summary = summary


def _parse_timestamp(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _format_timestamp(value: datetime | None) -> str:
    return value.isoformat(sep=" ") if value is not None else ""


def _parse_decimal(value: str) -> Decimal | None:
    value = value.strip()
    if not value:
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def _format_decimal(value: str) -> str:
    parsed = _parse_decimal(value)
    return format(parsed, "f") if parsed is not None else value.strip()


def _transform_row(raw: dict[str, str]) -> dict[str, str]:
    shipping_value = raw.get("shipping_limit_date", "")
    shipping_at = _parse_timestamp(shipping_value)
    shipping_output = _format_timestamp(shipping_at) if shipping_at is not None else shipping_value.strip()
    price = raw.get("price", "")
    freight_value = raw.get("freight_value", "")
    parsed_price = _parse_decimal(price)
    parsed_freight = _parse_decimal(freight_value)

    return {
        "order_id": (raw.get("order_id") or "").strip(),
        "order_item_id": (raw.get("order_item_id") or "").strip(),
        "product_id": (raw.get("product_id") or "").strip(),
        "seller_id": (raw.get("seller_id") or "").strip(),
        "shipping_limit_at": shipping_output,
        "item_price": _format_decimal(price),
        "freight_value": _format_decimal(freight_value),
        "missing_shipping_limit_date": str(shipping_at is None and not shipping_value.strip()).lower(),
        "invalid_shipping_limit_date": str(shipping_at is None and bool(shipping_value.strip())).lower(),
        "invalid_price": str(parsed_price is None and bool(price.strip())).lower(),
        "invalid_freight_value": str(parsed_freight is None and bool(freight_value.strip())).lower(),
    }


def _read_and_transform(input_path: Path) -> tuple[list[dict[str, str]], ValidationSummary]:
    transformed: list[dict[str, str]] = []
    composite_keys: list[tuple[str, str]] = []
    null_counts = Counter()

    with input_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        actual_columns = tuple(reader.fieldnames or ())
        if actual_columns != RAW_COLUMNS:
            raise ValueError(
                "Unexpected order-items CSV columns. "
                f"Expected {list(RAW_COLUMNS)}, got {list(actual_columns)}"
            )

        for raw in reader:
            values = {
                "order_id": (raw.get("order_id") or "").strip(),
                "order_item_id": (raw.get("order_item_id") or "").strip(),
                "product_id": (raw.get("product_id") or "").strip(),
                "seller_id": (raw.get("seller_id") or "").strip(),
                "price": (raw.get("price") or "").strip(),
                "freight_value": (raw.get("freight_value") or "").strip(),
            }
            for name, value in values.items():
                if not value:
                    null_counts[name] += 1
            composite_keys.append((values["order_id"], values["order_item_id"]))
            transformed.append(_transform_row(raw))

    key_counts = Counter(composite_keys)
    duplicate_count = sum(count - 1 for count in key_counts.values() if count > 1)
    invalid_date_count = sum(row["invalid_shipping_limit_date"] == "true" for row in transformed)
    invalid_numeric_count = sum(
        row["invalid_price"] == "true" or row["invalid_freight_value"] == "true"
        for row in transformed
    )
    summary = ValidationSummary(
        total_rows=len(transformed),
        unique_order_id_count=len({key[0] for key in composite_keys}),
        unique_composite_key_count=len(key_counts),
        duplicate_composite_key_count=duplicate_count,
        null_order_id_count=null_counts["order_id"],
        null_order_item_id_count=null_counts["order_item_id"],
        null_product_id_count=null_counts["product_id"],
        null_seller_id_count=null_counts["seller_id"],
        null_price_count=null_counts["price"],
        null_freight_value_count=null_counts["freight_value"],
        invalid_date_count=invalid_date_count,
        invalid_numeric_count=invalid_numeric_count,
    )

    structural_errors = []
    for field in ("order_id", "order_item_id", "product_id", "seller_id", "price", "freight_value"):
        count = getattr(summary, f"null_{field.replace('order_item_id', 'order_item_id').replace('freight_value', 'freight_value')}_count")
        if count:
            structural_errors.append(f"null {field} values={count}")
    if summary.duplicate_composite_key_count:
        structural_errors.append(
            "duplicate (order_id, order_item_id) rows="
            f"{summary.duplicate_composite_key_count}"
        )
    if structural_errors:
        raise StructuralValidationError(
            "Order-items structural validation failed: " + "; ".join(structural_errors),
            summary,
        )

    return transformed, summary


def transform_order_items(input_path: str | Path, output_path: str | Path) -> ValidationSummary:
    """Transform raw order items without joining, aggregating, or dropping rows."""
    transformed, summary = _read_and_transform(Path(input_path))
    output_file = Path(output_path)
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
    parser.add_argument("--input", type=Path, default=Path("data/raw/olist_order_items_dataset.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/stg_order_items.csv"))
    args = parser.parse_args()
    summary = transform_order_items(args.input, args.output)
    _print_summary(summary)
    print(f"Wrote: {args.output}")


if __name__ == "__main__":
    main()
