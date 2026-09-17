# Products Staging Transformation

## Purpose

`stg_products` is the clean staging representation of the Olist product master. It preserves product-level attributes for later product and category analysis.

- Source: `data/raw/olist_products_dataset.csv`
- Staging output: `data/processed/stg_products.csv`
- Grain: one row per product
- Natural key: `product_id`

## Source-to-staging mapping

| Raw column | Staging column | Treatment |
| --- | --- | --- |
| `product_id` | `product_id` | Trimmed string identifier |
| `product_category_name` | `product_category_name` | Trimmed text; missing values remain empty |
| `product_name_lenght` | `product_name_length` | Numeric value; source spelling corrected |
| `product_description_lenght` | `product_description_length` | Numeric value; source spelling corrected |
| `product_photos_qty` | `product_photos_qty` | Numeric value preserved |
| `product_weight_g` | `product_weight_g` | Numeric value preserved |
| `product_length_cm` | `product_length_cm` | Numeric value preserved |
| `product_height_cm` | `product_height_cm` | Numeric value preserved |
| `product_width_cm` | `product_width_cm` | Numeric value preserved |

The only source column renames are `lenght` to `length` for the two affected fields. No source attributes are dropped.

## Transformations and data-quality rules

- Required source columns are checked before processing.
- `product_id` is trimmed and must be non-null and unique.
- Product category values are trimmed. Missing categories remain empty and receive `missing_product_category=true`; no category is invented.
- Numeric values are parsed with `Decimal` and written without unnecessary rounding.
- Empty numeric values remain empty and are distinct from invalid non-empty text.
- Invalid numeric text is preserved exactly in the staging field and receives its corresponding `invalid_*` flag. It is never replaced with zero.
- Duplicate product IDs and null product IDs are structural failures. The transformation reports them and does not write an output file.
- No joins or aggregations are performed.

## Validation result for the current source

The real-data validation summary from `python -m src.transform_products` is:

```text
source rows: 32951
output rows: 32951
unique product_id count: 32951
duplicate product_id count: 0
null product_id count: 0
missing category count: 610
invalid product_name_length count: 0
invalid product_description_length count: 0
invalid product_photos_qty count: 0
invalid product_weight_g count: 0
invalid product_length_cm count: 0
invalid product_height_cm count: 0
invalid product_width_cm count: 0
```

These values are reported from the current source run; the transformation does not hardcode expected row counts.

## Known limitations

- No joins are performed with order items, orders, sellers, or category translations.
- No sales metrics are calculated.
- Product attributes remain at product grain. Revenue, units sold, order count, and sales rank belong in later analytical models.
- Missing product attributes remain missing and require an explicit policy in a later analytical layer.

## Why this table is not aggregated

One row represents one product identified by `product_id`. Keeping this master-data grain allows `stg_order_items.product_id` to relate to one product record later without multiplying product attributes. Sales and demand metrics must be calculated from the order-items fact, not stored here.

## Future relationship

The later analytical relationship will be:

```text
stg_order_items.product_id
    -> stg_products.product_id
```

This transformation intentionally does not implement that join.
