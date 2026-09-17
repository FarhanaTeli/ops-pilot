# Payments Staging Transformation

## Purpose

`stg_payments` is the clean staging representation of payment records from the Olist dataset. It preserves payment-level detail for later payment and revenue analysis.

- Source: `data/raw/olist_order_payments_dataset.csv`
- Staging output: `data/processed/stg_payments.csv`
- Grain: one row per payment record
- Natural/composite key: `(order_id, payment_sequential)`

`payment_sequential` is part of the natural key because one order can contain multiple payment records.

## Columns

| Source column | Staging column | Treatment |
| --- | --- | --- |
| `order_id` | `order_id` | Trimmed string identifier |
| `payment_sequential` | `payment_sequential` | Integer-like value when valid; invalid source text preserved |
| `payment_type` | `payment_type` | Trimmed source category; not inferred or replaced |
| `payment_installments` | `payment_installments` | Integer-like value when valid; invalid source text preserved |
| `payment_value` | `payment_value` | Decimal value when valid; invalid source text preserved |

The output also includes `missing_payment_type`, `invalid_payment_sequential`, `invalid_payment_installments`, and `invalid_payment_value`.

## Transformation rules

- Required source columns are checked before processing.
- IDs and payment categories are trimmed.
- Valid integer fields are normalized without changing their numeric meaning.
- Valid payment values are parsed with `Decimal` and written without unnecessary rounding.
- Missing payment type is preserved and flagged.
- Invalid non-empty numeric source text is preserved in the staging field and flagged. It is never silently replaced with zero or another valid value.
- Negative and zero payment values are counted for review; they are not silently removed.
- No joins or aggregations are performed.

## Data-quality rules

- `order_id` must be non-null.
- `payment_sequential` must be non-null and valid for the composite key.
- `(order_id, payment_sequential)` must be unique.
- `payment_type` missing values are reported but are not structural failures.
- Invalid numeric values are reported through explicit flags.
- The source row count is preserved when structural validation passes.
- Structural failures reject the complete input and do not write an output file.

## Validation results for the current source

The real-data validation summary from `python -m src.transform_payments` is:

```text
source rows: 103886
output rows: 103886
unique order_id count: 99440
unique composite key count: 103886
duplicate composite key count: 0
null order_id count: 0
null payment_sequential count: 0
null payment_type count: 0
invalid payment_sequential count: 0
invalid payment_installments count: 0
invalid payment_value count: 0
negative payment_value count: 0
zero payment_value count: 9
```

These values are reported from the current source run; the transformation does not hardcode expected row counts.

## Why payments are not aggregated at staging level

One order can contain multiple payment records, including different payment methods or sequences. Aggregating by `order_id` here would destroy payment-level detail and could cause incorrect joins or financial totals later. Order-level payment summaries belong in a later analytical model or view.

## How to run

```text
python -m src.transform_payments
```

The command reads the raw CSV and writes the ignored processed CSV under `data/processed/`.

## How to test

If pytest is installed:

```text
python -m pytest tests/test_transform_payments.py -q
```

The repository also supports direct standard-library smoke checks when pytest is unavailable.
