# NorthStar

NorthStar processes synthetic retail transactions, predicts customer churn, and
generates retention offers grounded in retailer policies. The repository also
defines AWS infrastructure and a pipeline that tests, trains, evaluates, and
registers churn models after changes to the main branch.

## Infrastructure and data processing

Terraform modules define networking, IAM roles, encrypted versioned S3 storage,
SageMaker Studio, Glue jobs, and a Feature Store group. LocalStack configuration
supports local infrastructure validation.

The Glue transform cleans and deduplicates transaction records, handles missing
values, and writes transaction-level Parquet. Feature engineering aggregates
customer history into 11 numeric model inputs, including recency, purchase
frequency, spending, basket size, category diversity, and channel mix.

Feature windows end on April 1, 2026. Churn labels use the subsequent observation
period through June 30, 2026. The Glue feature job and the unit tests share the
functions in `data/feature_engineering.py`. Outputs are written to S3 and the
online and offline Feature Store.

## Churn prediction

The model uses XGBoost with a stratified training and holdout split. Evaluation
includes precision and recall among the highest-scoring 10% of customers,
ROC AUC, a recency-only baseline, and a paired-bootstrap confidence interval
for AUC improvement. Loyalty-tier slices expose differences in recall.

Lab 3 experiment scripts log hyperparameters and metrics to a SageMaker MLflow
App. The inference handler returns churn probabilities from a saved model.
Saved model artifacts, predictions, experiment results, and evaluation evidence
are under `docs/lab3-evidence/`.

## Policy-grounded retention offers

`rag/offer_pipeline.py` retrieves policy passages using Titan embeddings and
a local FAISS index. Bedrock Claude Haiku generates category copy, while a
renderer derives incentive terms from retrieved policy and states eligibility
conditions. Profile validation and output checks reject unsupported categories,
malformed drafts, and ungrounded benefit claims.

The policy corpus is in `northstar-policy-docs/`; prompts are in
`prompt_templates/`. Saved evaluations compare retrieval strategies and record
faithfulness, answer relevance, context recall, safety cases, and model usage.
`notebooks/lab3-demo.ipynb` contains executed examples.

## Continuous integration and model registration

`pipeline.yaml` defines CodePipeline, CodeBuild, SNS notifications, and a
CloudWatch build-failure alarm. `buildspec.yml` receives a GitHub main-branch
revision and performs these steps:

1. Validate source data, processed data, feature values, and feature freshness.
2. Package the training code and run SageMaker managed Spot training.
3. Enforce precision >= 0.50, recall >= 0.25, and a positive lower confidence
   bound for AUC improvement over the baseline.
4. Register the candidate, attach code/data/metrics lineage, and test its saved
   artifact against the newest Approved model. Candidate AUC may regress by
   at most 0.02.
5. Leave a passing candidate PendingManualApproval for a separate promotion
   decision. Reject it if a later build gate fails.

A loyalty-tier recall gap above 0.10 produces a review warning. A failed test
stops the build; CloudWatch uses the native CodeBuild FailedBuilds metric to
notify the SNS subscription.

The test suite contains 72 data, feature, model, and fairness tests. Missing
inputs fail by default, and feature generations older than 48 hours fail the
freshness check. Evidence-export and verification scripts are in `scripts/`;
saved CI logs and registry descriptions are in `docs/`.

The repository does not deploy a production inference endpoint. Scheduled
retraining, production drift monitoring, and automatic rollback are not
implemented. Required lab assessments and reports remain under `docs/`, and
the supplied course reference documents are under `docs/reference/`.
