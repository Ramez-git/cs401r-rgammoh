# Data Contract: processed/customers

Version: 1.0. Owner: NorthStar Data Engineering. Region: us-east-1.

## Producer

Glue ETL job `northstar-dev-transform`, running as `northstar-dev-DataEngineer`.
Input: `s3://northstar-dev-data-{account-id}/raw/customers/` (CSV).
Output: `s3://northstar-dev-data-{account-id}/processed/customers/` (Parquet).
Each successful run overwrites this derived snapshot; S3 versioning retains prior
object versions according to the lifecycle policy. Readers must wait for SUCCEEDED:
multi-object S3 overwrite is not an atomic dataset publication.

## Consumers

- `northstar-dev-feature-engineer`, running as DataEngineer.
- Future model-training data preparation in Lab 3.

## Grain

One row per transaction, uniquely identified by `transaction_id`. Repeated
`customer_id` values are expected and preserve the purchase history.

## Schema

| Column | Spark / Parquet logical type | Nullable | Description |
|---|---|---|---|
| transaction_id | string | No | Natural transaction key; one row per purchase |
| customer_id | string | No | Customer join key, trimmed of whitespace |
| purchase_date | date | No | Purchase calendar date; rendered as YYYY-MM-DD |
| order_value | double | No | Gross order value in USD, finite and >= 0 |
| num_items | integer | No | Items per purchase, integer >= 1 |
| payment_method | string | No | Payment method, or `unknown` |
| channel | string | No | `store`, `online`, or `unknown` |
| store_id | string | No | Store identifier, `ONLINE`, or `unknown` |
| product_category | string | No | Primary product category, or `unknown` |

Parquet is typed; nullability above describes the data guarantee, even if Spark's
physical schema conservatively marks a field nullable.

## Quality Guarantees

1. Zero null or blank customer IDs; records without a customer are dropped.
2. Zero null transaction IDs and zero duplicated transaction IDs.
3. Every purchase date parses from YYYY-MM-DD or MM/dd/yyyy to a real date.
   An unparseable date fails the producer quality gate rather than publishing.
4. `order_value` is finite and >= 0; `num_items` is >= 1. No artificial upper
   cap is imposed on legitimate large purchases. Invalid ranges fail publication.
5. Missing numeric values use exact column medians after type normalization,
   before deduplication; the item-count median is rounded to an integer.
   An entirely missing numeric column fails rather than inventing a replacement.
6. Missing descriptive strings become `unknown`. Unknown categories are excluded
   from downstream diversity counts.

Duplicates are resolved by purchase date descending, then order value descending,
then remaining fields ascending. Identical input yields identical cleaned values.
The full lab sample locally produced 157,627 processed rows from 163,255 raw rows;
these are validation observations, not fixed row-count guarantees for new inputs.

## SLA / Service Level

Target: processed data is available within 2 hours of landing in raw storage.
The lab pipeline is on demand: the operator must start the crawler and transform
and monitor their results within that period. No automatic scheduling or SLA alarm
is provisioned. On failure, consult CloudWatch `/aws-glue/` logs, correct the input
or code, rerun the producer, and notify consumers before resuming downstream jobs.

## Versioning and Breaking Changes

Schema changes require a new prefix, for example `processed/customers/v2/`.
Notify consumers at least 5 business days before a breaking change; retain the old
prefix until consumers migrate. Changes to units, grain, date meaning, or imputation
semantics also require a version change. Raw current objects expire at 90 days;
raw and processed noncurrent versions expire at 30 days, feature noncurrent
versions at 60 days, and datacapture current objects at 7 days.

## Downstream temporal contract

Features use only history on or before 2026-04-01. Rolling N-day windows are
`(2026-04-01 - N days, 2026-04-01]`. Customers with no observation history are
excluded. The label is 1 if there is no purchase in `(2026-04-01, 2026-06-30]`.
Customers seen only after the cutoff cannot receive historical features.
`churn_risk_score` is a baseline heuristic, separate from `churn_label`.
Feature Store `event_time` records ingestion epoch seconds, not the feature cutoff.
Training consumers should select one ingestion snapshot and must not use the
customer identifier or ingestion timestamp as predictive inputs.
