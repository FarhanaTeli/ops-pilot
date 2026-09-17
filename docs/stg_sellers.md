# Sellers Staging Transformation

## Objective

`stg_sellers` is the clean staging representation of the Olist seller master. It preserves seller-level identity and location attributes for later seller analysis.

- Source: `data/raw/olist_sellers_dataset.csv`
- Staging output: `data/processed/stg_sellers.csv`
- Grain: one row per seller
- Natural key: `seller_id`

## Columns

| Source column | Staging column | Treatment |
| --- | --- | --- |
| `seller_id` | `seller_id` | Trimmed string identifier |
| `seller_zip_code_prefix` | `seller_zip_code_prefix` | Trimmed text; leading zeros preserved |
| `seller_city` | `seller_city` | Trimmed text |
| `seller_state` | `seller_state` | Trimmed text |

The output also includes `invalid_seller_zip_code_prefix`.

## Transformation rules

- Required source columns are checked before processing.
- `seller_id`, city, and state values are trimmed.
- ZIP prefixes remain text so values such as `01323` retain their leading zero.
- A non-empty ZIP prefix is considered valid when it contains digits only.
- No geolocation or other table is joined.
- No aggregation or enrichment is performed.

## Validation rules

- `seller_id` must be non-null.
- `seller_id` must be unique.
- The source row count is preserved when structural validation passes.
- Invalid non-empty ZIP text is preserved in `seller_zip_code_prefix` and flagged with `invalid_seller_zip_code_prefix=true`.
- Missing ZIP prefixes remain empty and are not classified as invalid ZIP text.
- Null seller IDs and duplicate seller IDs are structural failures. The transformation reports the issue and does not write an output file.

## Validation results for the current source

The real-data validation summary from `python -m src.transform_sellers` is:

```text
source rows: 3095
output rows: 3095
unique seller_id count: 3095
duplicate seller_id count: 0
null seller_id count: 0
invalid seller_zip_code_prefix count: 0
```

These values are reported from the current source run; the transformation does not hardcode expected row counts.

## Rejected-record behavior

The transformation rejects the complete input rather than silently dropping rows when required columns are missing, `seller_id` is null, or `seller_id` is duplicated. Invalid ZIP text is not a structural failure: it remains visible in the output and receives an explicit validation flag.

## Known limitations

- This slice does not join `seller_zip_code_prefix` to geolocation.
- ZIP prefix validation checks the source representation, not whether the prefix exists in a geographic lookup.
- Seller performance, revenue, order counts, and delivery metrics belong in later analytical models.

## Why this table is not aggregated

One row represents one seller identified by `seller_id`. Keeping this master-data grain allows later facts such as `stg_order_items` to relate seller attributes without multiplying seller records. Seller sales and operational metrics must be calculated from event facts, not stored in this staging table.
