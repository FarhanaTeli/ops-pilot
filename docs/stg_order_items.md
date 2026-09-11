# Order Items Staging Transformation

## Purpose

`stg_order_items` is the clean staging representation of Olist item-level sales transactions. It preserves the source transaction grain so later analytical models can calculate sales, product, and seller metrics without losing detail.

- Source: `data/raw/olist_order_items_dataset.csv`
- Staging output: `data/processed/stg_order_items.csv`
- Grain: one row per order item
- Natural key: `(order_id, order_item_id)`

## Column mapping

| Raw column | Staging column | Treatment |
| --- | --- | --- |
| `order_id` | `order_id` | Trimmed string identifier |
| `order_item_id` | `order_item_id` | Trimmed string sequence identifier |
| `product_id` | `product_id` | Trimmed string identifier |
| `seller_id` | `seller_id` | Trimmed string identifier |
| `shipping_limit_date` | `shipping_limit_at` | Parsed and standardized timestamp |
| `price` | `item_price` | Parsed as decimal without unnecessary rounding |
| `freight_value` | `freight_value` | Parsed as decimal without unnecessary rounding |

The output also includes `missing_shipping_limit_date`, `invalid_shipping_limit_date`, `invalid_price`, and `invalid_freight_value` flags.

## Transformations and data-quality rules

- Required source columns are checked before processing.
- Required identifiers and monetary values must be non-null.
- The composite key `(order_id, order_item_id)` must be unique.
- IDs are trimmed and retained as strings.
- Valid timestamps are converted to a standard `YYYY-MM-DD HH:MM:SS` representation.
- Missing shipping dates remain empty and receive `missing_shipping_limit_date=true`.
- Invalid, non-empty shipping dates are not repaired; the original text is retained in `shipping_limit_at` and `invalid_shipping_limit_date=true` marks it as unusable as a timestamp.
- Valid monetary values are parsed through `Decimal` and written without unnecessary rounding.
- Invalid non-empty numeric values are preserved as source text and flagged with `invalid_price` or `invalid_freight_value`.
- Null mandatory fields and duplicate composite keys are structural failures. The transformation reports them and does not write an output file.

## Validation result for the current source

The real-data validation summary from `python -m src.transform_order_items` is:

```text
source rows: 112650
output rows: 112650
unique order_id count: 98666
unique composite key count: 112650
duplicate composite key count: 0
null mandatory field counts: 0 for every mandatory field
invalid date count: 0
invalid numeric count: 0
```

These counts are reported from the current source run; the transformation does not hardcode expected row counts.

## Known limitations

- No joins are performed with orders, products, sellers, payments, or other tables.
- No aggregation is performed.
- `item_price` and `freight_value` remain item-level values; order revenue and order totals belong in later analytical models.
- Invalid source values are flagged for investigation rather than silently corrected.

## Why this table is not aggregated

One row represents one order item identified by `(order_id, order_item_id)`. Keeping this grain allows later analysis to group safely by product, seller, order, customer, or date. Aggregating now would hide item-level detail and make it harder to avoid double counting when other one-to-many tables are introduced.
