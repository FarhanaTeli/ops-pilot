"""Transform raw Olist products into the stg_products dataset."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

RAW_COLUMNS = (
    "product_id",
    "product_category_name",
    "product_name_lenght",
    "product_description_lenght",
    "product_photos_qty",
    "product_weight_g",
    "product_length_cm",
    "product_height_cm",
    "product_width_cm",
)

NUMERIC_COLUMNS = (
    "product_name_lenght",
    "product_description_lenght",
    "product_photos_qty",
    "product_weight_g",
    "product_length_cm",
    "product_height_cm",
    "product_width_cm",
)

STAGING_COLUMNS = (
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
)

NUMERIC_RENAMES = {
    "product_name_lenght": "product_name_length",
    "product_description_lenght": "product_description_length",
}


@dataclass(frozen=True)
class ValidationSummary:
    """Counts produced while validating and transforming products."""

    total_rows: int
    unique_product_id_count: int
    duplicate_product_id_count: int
    null_product_id_count: int
    missing_category_count: int
    invalid_numeric_counts: dict[str, int]

    def as_dict(self) -> dict[str, int]:
        values = {
            "total_rows": self.total_rows,
            "unique_product_id_count": self.unique_product_id_count,
            "duplicate_product_id_count": self.duplicate_product_id_count,
            "null_product_id_count": self.null_product_id_count,
            "missing_category_count": self.missing_category_count,
        }
        values.update(
            {
                f"invalid_{field}_count": count
                for field, count in self.invalid_numeric_counts.items()
            }
        )
        return values


class StructuralValidationError(ValueError):
    """Raised when the input cannot safely represent one row per product."""

    def __init__(self, message: str, summary: ValidationSummary):
        super().__init__(message)
        self.summary = summary


def _parse_decimal(value: str) -> Decimal | None:
    value = value.strip()
    if not value:
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def _format_numeric(value: str) -> str:
    parsed = _parse_decimal(value)
    return format(parsed, "f") if parsed is not None else value.strip()


def _invalid_flag_name(source_column: str) -> str:
    return f"invalid_{NUMERIC_RENAMES.get(source_column, source_column)}"


def _transform_row(raw: dict[str, str]) -> dict[str, str]:
    output = {
        "product_id": (raw.get("product_id") or "").strip(),
        "product_category_name": (raw.get("product_category_name") or "").strip(),
    }
    for source_column in NUMERIC_COLUMNS:
        staging_column = NUMERIC_RENAMES.get(source_column, source_column)
        raw_value = (raw.get(source_column) or "").strip()
        output[staging_column] = _format_numeric(raw_value)

    output["missing_product_category"] = str(
        not output["product_category_name"]
    ).lower()
    for source_column in NUMERIC_COLUMNS:
        raw_value = (raw.get(source_column) or "").strip()
        flag_name = _invalid_flag_name(source_column)
        output[flag_name] = str(
            bool(raw_value) and _parse_decimal(raw_value) is None
        ).lower()
    return output


def _read_and_transform(input_path: Path) -> tuple[list[dict[str, str]], ValidationSummary]:
    transformed: list[dict[str, str]] = []
    product_ids: list[str] = []
    null_product_id_count = 0
    missing_category_count = 0
    invalid_numeric_counts = Counter()

    with input_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        actual_columns = tuple(reader.fieldnames or ())
        if actual_columns != RAW_COLUMNS:
            raise ValueError(
                "Unexpected products CSV columns. "
                f"Expected {list(RAW_COLUMNS)}, got {list(actual_columns)}"
            )

        for raw in reader:
            product_id = (raw.get("product_id") or "").strip()
            product_ids.append(product_id)
            null_product_id_count += not bool(product_id)
            missing_category_count += not (raw.get("product_category_name") or "").strip()
            row = _transform_row(raw)
            transformed.append(row)
            for source_column in NUMERIC_COLUMNS:
                if row[_invalid_flag_name(source_column)] == "true":
                    invalid_numeric_counts[NUMERIC_RENAMES.get(source_column, source_column)] += 1

    id_counts = Counter(product_ids)
    duplicate_product_id_count = sum(
        count - 1 for count in id_counts.values() if count > 1
    )
    summary = ValidationSummary(
        total_rows=len(transformed),
        unique_product_id_count=len(id_counts),
        duplicate_product_id_count=duplicate_product_id_count,
        null_product_id_count=null_product_id_count,
        missing_category_count=missing_category_count,
        invalid_numeric_counts={
            NUMERIC_RENAMES.get(field, field): invalid_numeric_counts[
                NUMERIC_RENAMES.get(field, field)
            ]
            for field in NUMERIC_COLUMNS
        },
    )

    structural_errors = []
    if summary.null_product_id_count:
        structural_errors.append(
            f"null product_id values={summary.null_product_id_count}"
        )
    if summary.duplicate_product_id_count:
        structural_errors.append(
            f"duplicate product_id rows={summary.duplicate_product_id_count}"
        )
    if structural_errors:
        raise StructuralValidationError(
            "Products structural validation failed: " + "; ".join(structural_errors),
            summary,
        )

    return transformed, summary


def transform_products(input_path: str | Path, output_path: str | Path) -> ValidationSummary:
    """Transform raw products without joining or aggregating rows."""
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
    parser.add_argument("--input", type=Path, default=Path("data/raw/olist_products_dataset.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/stg_products.csv"))
    args = parser.parse_args()
    summary = transform_products(args.input, args.output)
    _print_summary(summary)
    print(f"Wrote: {args.output}")


if __name__ == "__main__":
    main()
