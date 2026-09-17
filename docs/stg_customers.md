# Customers Staging Transformation

## Objective

`stg_customers` is the clean staging representation of customer records from the Olist dataset. It preserves the source customer-instance grain for later customer, geography, and repeat-purchase analysis.

- Source: `data/raw/olist_customers_dataset.csv`
- Staging output: `data/processed/stg_customers.csv`
- Grain: one row per `customer_id` record
- Primary key: `customer_id`

## Customer identity fields

- `customer_id` identifies the customer record associated with an order. It is the staging primary key and must be unique.
- `customer_unique_id` identifies the real-world customer across orders. It is intentionally allowed to repeat because one customer can have multiple customer records and orders.

The transformation does not deduplicate or aggregate by `customer_unique_id`.

## Columns

| Source column | Staging column | Treatment |
| --- | --- | --- |
| `customer_id` | `customer_id` | Trimmed string identifier |
| `customer_unique_id` | `customer_unique_id` | Trimmed source identity field; duplicates allowed |
| `customer_zip_code_prefix` | `customer_zip_code_prefix` | Trimmed text; leading zeros preserved |
| `customer_city` | `customer_city` | Trimmed text |
| `customer_state` | `customer_state` | Trimmed text |

The output also includes `invalid_customer_zip_code_prefix`.

## Transformation rules

- Required source columns are checked before processing.
- IDs and descriptive text are trimmed.
- ZIP prefixes remain text so values such as `01151` retain leading zeros.
- A non-empty ZIP prefix is considered valid when it contains digits only.
- Invalid ZIP text is preserved and flagged; it is not silently corrected.
- No geolocation or other table is joined.
- No aggregation or enrichment is performed.

## Validation rules

- `customer_id` must be non-null and unique.
- The source row count is preserved when structural validation passes.
- Repeated `customer_unique_id` values are expected and are not a validation failure.
- `invalid_customer_zip_code_prefix=true` identifies non-empty ZIP text that is not numeric.
- Missing ZIP prefixes remain empty and are not classified as invalid ZIP text.

## Rejected-record behavior

The transformation rejects the complete input rather than silently dropping rows when required columns are missing, `customer_id` is null, or `customer_id` is duplicated. Repeated `customer_unique_id` values do not cause rejection. Invalid ZIP text is retained in the output with an explicit flag.

## Validation results for the current source

The real-data validation summary from `python -m src.transform_customers` is:

```text
source rows: 99441
output rows: 99441
unique customer_id count: 99441
duplicate customer_id count: 0
null customer_id count: 0
unique customer_unique_id count: 96096
duplicate customer_unique_id count: 3345
invalid customer_zip_code_prefix count: 0
```

These values are reported from the current source run; the transformation does not hardcode expected row counts.

## Known limitations

- This slice does not join customer ZIP prefixes to geolocation.
- ZIP validation checks the source representation, not whether the prefix exists in a geographic lookup.
- Customer lifetime metrics and repeat-purchase metrics belong in later analytical models using `customer_unique_id`.

## Why this table is not aggregated

One row represents one source customer record identified by `customer_id`. Keeping that grain preserves the relationship from orders to customer records while allowing repeated `customer_unique_id` values to support real-world customer analysis later.
