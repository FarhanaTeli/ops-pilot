"""Transform raw Olist payments into the stg_payments dataset."""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

RAW_COLUMNS = (
    "order_id",
    "payment_sequential",
    "payment_type",
    "payment_installments",
    "payment_value",
)

STAGING_COLUMNS = (
    "order_id",
    "payment_sequential",
    "payment_type",
    "payment_installments",
    "payment_value",
    "missing_payment_type",
    "invalid_payment_sequential",
    "invalid_payment_installments",
    "invalid_payment_value",
)

_INTEGER_PATTERN = re.compile(r"^[+-]?\d+$")


@dataclass(frozen=True)
class ValidationSummary:
    """Counts produced while validating and transforming payments."""

    total_rows: int
    unique_order_id_count: int
    unique_composite_key_count: int
    duplicate_composite_key_count: int
    null_order_id_count: int
    null_payment_sequential_count: int
    null_payment_type_count: int
    invalid_payment_sequential_count: int
    invalid_payment_installments_count: int
    invalid_payment_value_count: int
    negative_payment_value_count: int
    zero_payment_value_count: int

    def as_dict(self) -> dict[str, int]:
        return {
            "total_rows": self.total_rows,
            "unique_order_id_count": self.unique_order_id_count,
            "unique_composite_key_count": self.unique_composite_key_count,
            "duplicate_composite_key_count": self.duplicate_composite_key_count,
            "null_order_id_count": self.null_order_id_count,
            "null_payment_sequential_count": self.null_payment_sequential_count,
            "null_payment_type_count": self.null_payment_type_count,
            "invalid_payment_sequential_count": self.invalid_payment_sequential_count,
            "invalid_payment_installments_count": self.invalid_payment_installments_count,
            "invalid_payment_value_count": self.invalid_payment_value_count,
            "negative_payment_value_count": self.negative_payment_value_count,
            "zero_payment_value_count": self.zero_payment_value_count,
        }


class StructuralValidationError(ValueError):
    """Raised when the input cannot safely represent one row per payment record."""

    def __init__(self, message: str, summary: ValidationSummary):
        super().__init__(message)
        self.summary = summary


def _parse_integer(value: str) -> int | None:
    value = value.strip()
    if not value or not _INTEGER_PATTERN.fullmatch(value):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _format_integer(value: str) -> str:
    parsed = _parse_integer(value)
    return str(parsed) if parsed is not None else value.strip()


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
    order_id = (raw.get("order_id") or "").strip()
    payment_sequential = (raw.get("payment_sequential") or "").strip()
    payment_type = (raw.get("payment_type") or "").strip()
    payment_installments = (raw.get("payment_installments") or "").strip()
    payment_value = (raw.get("payment_value") or "").strip()
    parsed_sequential = _parse_integer(payment_sequential)
    parsed_installments = _parse_integer(payment_installments)
    parsed_value = _parse_decimal(payment_value)

    return {
        "order_id": order_id,
        "payment_sequential": _format_integer(payment_sequential),
        "payment_type": payment_type,
        "payment_installments": _format_integer(payment_installments),
        "payment_value": _format_decimal(payment_value),
        "missing_payment_type": str(not payment_type).lower(),
        "invalid_payment_sequential": str(
            bool(payment_sequential) and parsed_sequential is None
        ).lower(),
        "invalid_payment_installments": str(
            bool(payment_installments) and parsed_installments is None
        ).lower(),
        "invalid_payment_value": str(
            bool(payment_value) and parsed_value is None
        ).lower(),
    }


def _read_and_transform(input_path: Path) -> tuple[list[dict[str, str]], ValidationSummary]:
    transformed: list[dict[str, str]] = []
    composite_keys: list[tuple[str, str]] = []
    order_ids: list[str] = []
    null_order_id_count = 0
    null_payment_sequential_count = 0
    null_payment_type_count = 0
    invalid_sequential_count = 0
    invalid_installments_count = 0
    invalid_value_count = 0
    negative_value_count = 0
    zero_value_count = 0

    with input_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        actual_columns = tuple(reader.fieldnames or ())
        if actual_columns != RAW_COLUMNS:
            raise ValueError(
                "Unexpected payments CSV columns. "
                f"Expected {list(RAW_COLUMNS)}, got {list(actual_columns)}"
            )

        for raw in reader:
            order_id = (raw.get("order_id") or "").strip()
            payment_sequential = (raw.get("payment_sequential") or "").strip()
            payment_type = (raw.get("payment_type") or "").strip()
            payment_value = (raw.get("payment_value") or "").strip()
            parsed_value = _parse_decimal(payment_value)
            row = _transform_row(raw)
            transformed.append(row)
            order_ids.append(order_id)
            composite_keys.append((order_id, payment_sequential))
            null_order_id_count += not bool(order_id)
            null_payment_sequential_count += not bool(payment_sequential)
            null_payment_type_count += not bool(payment_type)
            invalid_sequential_count += row["invalid_payment_sequential"] == "true"
            invalid_installments_count += row["invalid_payment_installments"] == "true"
            invalid_value_count += row["invalid_payment_value"] == "true"
            if parsed_value is not None:
                negative_value_count += parsed_value < 0
                zero_value_count += parsed_value == 0

    key_counts = Counter(composite_keys)
    summary = ValidationSummary(
        total_rows=len(transformed),
        unique_order_id_count=len(set(order_ids)),
        unique_composite_key_count=len(key_counts),
        duplicate_composite_key_count=sum(
            count - 1 for count in key_counts.values() if count > 1
        ),
        null_order_id_count=null_order_id_count,
        null_payment_sequential_count=null_payment_sequential_count,
        null_payment_type_count=null_payment_type_count,
        invalid_payment_sequential_count=invalid_sequential_count,
        invalid_payment_installments_count=invalid_installments_count,
        invalid_payment_value_count=invalid_value_count,
        negative_payment_value_count=negative_value_count,
        zero_payment_value_count=zero_value_count,
    )

    structural_errors = []
    if summary.null_order_id_count:
        structural_errors.append(
            f"null order_id values={summary.null_order_id_count}"
        )
    if summary.null_payment_sequential_count:
        structural_errors.append(
            "null payment_sequential values="
            f"{summary.null_payment_sequential_count}"
        )
    if summary.duplicate_composite_key_count:
        structural_errors.append(
            "duplicate (order_id, payment_sequential) rows="
            f"{summary.duplicate_composite_key_count}"
        )
    if structural_errors:
        raise StructuralValidationError(
            "Payments structural validation failed: " + "; ".join(structural_errors),
            summary,
        )

    return transformed, summary


def transform_payments(input_path: str | Path, output_path: str | Path) -> ValidationSummary:
    """Transform raw payments without joining, aggregating, or dropping rows."""
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
    parser.add_argument("--input", type=Path, default=Path("data/raw/olist_order_payments_dataset.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/stg_payments.csv"))
    args = parser.parse_args()
    summary = transform_payments(args.input, args.output)
    _print_summary(summary)
    print(f"Wrote: {args.output}")


if __name__ == "__main__":
    main()
