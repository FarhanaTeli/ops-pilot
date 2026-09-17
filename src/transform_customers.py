"""Transform raw Olist customers into the stg_customers dataset."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

RAW_COLUMNS = (
    "customer_id",
    "customer_unique_id",
    "customer_zip_code_prefix",
    "customer_city",
    "customer_state",
)

STAGING_COLUMNS = (
    "customer_id",
    "customer_unique_id",
    "customer_zip_code_prefix",
    "customer_city",
    "customer_state",
    "invalid_customer_zip_code_prefix",
)


@dataclass(frozen=True)
class ValidationSummary:
    """Counts produced while validating and transforming customers."""

    total_rows: int
    unique_customer_id_count: int
    duplicate_customer_id_count: int
    null_customer_id_count: int
    unique_customer_unique_id_count: int
    duplicate_customer_unique_id_count: int
    invalid_customer_zip_code_prefix_count: int

    def as_dict(self) -> dict[str, int]:
        return {
            "total_rows": self.total_rows,
            "unique_customer_id_count": self.unique_customer_id_count,
            "duplicate_customer_id_count": self.duplicate_customer_id_count,
            "null_customer_id_count": self.null_customer_id_count,
            "unique_customer_unique_id_count": self.unique_customer_unique_id_count,
            "duplicate_customer_unique_id_count": self.duplicate_customer_unique_id_count,
            "invalid_customer_zip_code_prefix_count": self.invalid_customer_zip_code_prefix_count,
        }


class StructuralValidationError(ValueError):
    """Raised when the input cannot safely represent one row per customer record."""

    def __init__(self, message: str, summary: ValidationSummary):
        super().__init__(message)
        self.summary = summary


def _is_valid_zip_prefix(value: str) -> bool:
    """Validate a ZIP prefix without converting away leading zeros."""
    return bool(value) and value.isdigit()


def _transform_row(raw: dict[str, str]) -> dict[str, str]:
    zip_prefix = (raw.get("customer_zip_code_prefix") or "").strip()
    return {
        "customer_id": (raw.get("customer_id") or "").strip(),
        "customer_unique_id": (raw.get("customer_unique_id") or "").strip(),
        "customer_zip_code_prefix": zip_prefix,
        "customer_city": (raw.get("customer_city") or "").strip(),
        "customer_state": (raw.get("customer_state") or "").strip(),
        "invalid_customer_zip_code_prefix": str(
            bool(zip_prefix) and not _is_valid_zip_prefix(zip_prefix)
        ).lower(),
    }


def _read_and_transform(input_path: Path) -> tuple[list[dict[str, str]], ValidationSummary]:
    transformed: list[dict[str, str]] = []
    customer_ids: list[str] = []
    customer_unique_ids: list[str] = []
    null_customer_id_count = 0
    invalid_zip_count = 0

    with input_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        actual_columns = tuple(reader.fieldnames or ())
        if actual_columns != RAW_COLUMNS:
            raise ValueError(
                "Unexpected customers CSV columns. "
                f"Expected {list(RAW_COLUMNS)}, got {list(actual_columns)}"
            )

        for raw in reader:
            customer_id = (raw.get("customer_id") or "").strip()
            customer_unique_id = (raw.get("customer_unique_id") or "").strip()
            customer_ids.append(customer_id)
            customer_unique_ids.append(customer_unique_id)
            null_customer_id_count += not bool(customer_id)
            row = _transform_row(raw)
            transformed.append(row)
            invalid_zip_count += row["invalid_customer_zip_code_prefix"] == "true"

    customer_id_counts = Counter(customer_ids)
    customer_unique_id_counts = Counter(customer_unique_ids)
    summary = ValidationSummary(
        total_rows=len(transformed),
        unique_customer_id_count=len(customer_id_counts),
        duplicate_customer_id_count=sum(
            count - 1 for count in customer_id_counts.values() if count > 1
        ),
        null_customer_id_count=null_customer_id_count,
        unique_customer_unique_id_count=len(customer_unique_id_counts),
        duplicate_customer_unique_id_count=sum(
            count - 1 for count in customer_unique_id_counts.values() if count > 1
        ),
        invalid_customer_zip_code_prefix_count=invalid_zip_count,
    )

    structural_errors = []
    if summary.null_customer_id_count:
        structural_errors.append(
            f"null customer_id values={summary.null_customer_id_count}"
        )
    if summary.duplicate_customer_id_count:
        structural_errors.append(
            f"duplicate customer_id rows={summary.duplicate_customer_id_count}"
        )
    if structural_errors:
        raise StructuralValidationError(
            "Customers structural validation failed: " + "; ".join(structural_errors),
            summary,
        )

    return transformed, summary


def transform_customers(input_path: str | Path, output_path: str | Path) -> ValidationSummary:
    """Transform raw customers without joining, aggregating, or deduplicating identities."""
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
    parser.add_argument("--input", type=Path, default=Path("data/raw/olist_customers_dataset.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/stg_customers.csv"))
    args = parser.parse_args()
    summary = transform_customers(args.input, args.output)
    _print_summary(summary)
    print(f"Wrote: {args.output}")


if __name__ == "__main__":
    main()
