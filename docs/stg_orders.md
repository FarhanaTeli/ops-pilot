# Orders Staging Transformation

## Source and staging table

- Source: `data/raw/olist_orders_dataset.csv`
- Staging output: `data/processed/stg_orders.csv`
- Grain: one row per `order_id`

## Transformations

The transformation:

- Renames lifecycle timestamps to clear `_at` names.
- Converts IDs to strings.
- Converts timestamp values to Python datetimes before writing them in ISO-like text form.
- Normalizes `order_status` to lowercase.
- Preserves missing timestamps as empty values.
- Preserves the raw row count unless structural validation fails.

## Validation flags

The output includes flags for missing lifecycle timestamps:

- `missing_approval_date`
- `missing_carrier_date`
- `missing_delivery_date`

It also includes chronological validation flags:

- `invalid_approval_date`: approval occurred before purchase.
- `invalid_carrier_date`: carrier handoff occurred before purchase.
- `invalid_delivery_date`: customer delivery occurred before purchase or before carrier handoff.
- `invalid_estimated_delivery_date`: estimated delivery occurred before purchase.
- `late_delivery`: customer delivery occurred after the estimated delivery date, evaluated only when both dates exist.

Invalid dates are flagged rather than corrected because the source value is evidence that may require investigation. Silently changing it would hide a data-quality problem and make the staging output impossible to audit against the source.

## Structural validation

The transformation requires non-null `order_id` and `customer_id`, and requires `order_id` to be unique. If these structural rules fail, the transformation raises a clear validation error and does not write a staging file. Duplicate or null records are not silently removed.
