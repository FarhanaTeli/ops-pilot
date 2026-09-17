"""Transform raw Olist sellers into the stg_sellers dataset."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

RAW_COLUMNS = (
    "seller_id",
    "seller_zip_code_prefix",
    "seller_city",
    "seller_state",
)

STAGING_COLUMNS = (
    "seller_id",
    "seller_zip_code_prefix",
    "seller_city",
    "seller_state",
    "invalid_seller_zip_code_prefix",
)


@dataclass(frozen=True)
class ValidationSummary:
    """Counts produced while validating and transforming sellers."""

    total_rows: int
    unique_seller_id_count: int
    duplicate_seller_id_count: int
    null_seller_id_count: int
    invalid_seller_zip_code_prefix_count: int

    def as_dict(self) -> dict[str, int]:
        return {
            "total_rows": self.total_rows,
            "unique_seller_id_count": self.unique_seller_id_count,
            "duplicate_seller_id_count": self.duplicate_seller_id_count,
            "null_seller_id_count": self.null_seller_id_count,
            "invalid_seller_zip_code_prefix_count": self.invalid_seller_zip_code_prefix_count,
        }


class StructuralValidationError(ValueError):
    """Raised when the input cannot safely represent one row per seller."""

    def __init__(self, message: str, summary: ValidationSummary):
        super().__init__(message)
        self.summary = summary


def _is_valid_zip_prefix(value: str) -> bool:
    """Validate a ZIP prefix without converting away leading zeros."""
    return bool(value) and value.isdigit()


def _transform_row(raw: dict[str, str]) -> dict[str, str]:
    zip_prefix = (raw.get("seller_zip_code_prefix") or "").strip()
    return {
        "seller_id": (raw.get("seller_id") or "").strip(),
        "seller_zip_code_prefix": zip_prefix,
        "seller_city": (raw.get("seller_city") or "").strip(),
        "seller_state": (raw.get("seller_state") or "").strip(),
        "invalid_seller_zip_code_prefix": str(
            bool(zip_prefix) and not _is_valid_zip_prefix(zip_prefix)
        ).lower(),
    }


def _read_and_transform(input_path: Path) -> tuple[list[dict[str, str]], ValidationSummary]:
    transformed: list[dict[str, str]] = []
    seller_ids: list[str] = []
    null_seller_id_count = 0
    invalid_zip_count = 0

    with input_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        actual_columns = tuple(reader.fieldnames or ())
        if actual_columns != RAW_COLUMNS:
            raise ValueError(
                "Unexpected sellers CSV columns. "
                f"Expected {list(RAW_COLUMNS)}, got {list(actual_columns)}"
            )

        for raw in reader:
            seller_id = (raw.get("seller_id") or "").strip()
            seller_ids.append(seller_id)
            null_seller_id_count += not bool(seller_id)
            row = _transform_row(raw)
            transformed.append(row)
            invalid_zip_count += row["invalid_seller_zip_code_prefix"] == "true"

    seller_id_counts = Counter(seller_ids)
    duplicate_seller_id_count = sum(
        count - 1 for count in seller_id_counts.values() if count > 1
    )
    summary = ValidationSummary(
        total_rows=len(transformed),
        unique_seller_id_count=len(seller_id_counts),
        duplicate_seller_id_count=duplicate_seller_id_count,
        null_seller_id_count=null_seller_id_count,
        invalid_seller_zip_code_prefix_count=invalid_zip_count,
    )

    structural_errors = []
    if summary.null_seller_id_count:
        structural_errors.append(
            f"null seller_id values={summary.null_seller_id_count}"
        )
    if summary.duplicate_seller_id_count:
        structural_errors.append(
            f"duplicate seller_id rows={summary.duplicate_seller_id_count}"
        )
    if structural_errors:
        raise StructuralValidationError(
            "Sellers structural validation failed: " + "; ".join(structural_errors),
            summary,
        )

    return transformed, summary


def transform_sellers(input_path: str | Path, output_path: str | Path) -> ValidationSummary:
    """Transform raw sellers without joining, aggregating, or dropping rows."""
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
    parser.add_argument("--input", type=Path, default=Path("data/raw/olist_sellers_dataset.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/stg_sellers.csv"))
    args = parser.parse_args()
    summary = transform_sellers(args.input, args.output)
    _print_summary(summary)
    print(f"Wrote: {args.output}")


if __name__ == "__main__":
    main()
