# NorthStar XOps assessment

## Pipeline Stage Mapping

CodePipeline fits the existing AWS platform and keeps execution roles, logs,
alarms and model artifacts together. Source watches GitHub's main branch.
Within the Build stage, CodeBuild's PRE_BUILD runs every test except the two
artifact-dependent suites. BUILD packages this commit's code, starts SageMaker
spot training, evaluates the held-out model and registers it
PendingManualApproval. Training rejects failed quality gates before registration.
CodeBuild then checks the actual artifact, approved champion and fairness
results; POST_BUILD rejects a registered candidate if those checks fail.
ManualApproval is the human promotion decision. These boundaries implement
Source → Test → Build → Evaluate → Register without five separate stages.

## Champion-Challenger

The champion is the newest Approved package. A candidate qualifies when
precision at the top decile is at least 0.50, recall at least 0.25, the paired
bootstrap 95% AUC-lift interval has a positive lower bound, and candidate AUC
is at least champion AUC minus 0.02. The first run has no champion; subsequent
runs must compare with one. A loyalty-tier recall gap above 0.10 creates a
visible review warning, not an automatic rejection. Passing gates creates a
candidate; approval remains a separate decision.

## Retraining Triggers

These triggers are designed, not deployed. EventBridge Scheduler would invoke
a Step Functions workflow at cron(0 8 ? * MON *) in UTC. It would refresh
Glue features, wait for success, and start CodePipeline. For performance,
a daily labeled-production evaluation would publish NorthStar/Model AUC.
A CloudWatch alarm would trigger the same workflow through EventBridge when
AUC is below 0.70 for two consecutive daily periods, each containing at least
1,000 labeled customers and 100 positive labels. Missing or insufficient
labels would alert without starting retraining.

## DataOps Maturity

Current level: 2, automated.

Evidence: Terraform modules under infrastructure/modules/ define IAM,
networking, storage, Glue and Feature Store. glue-scripts/transform.py
preserves transaction grain; data/feature_engineering.py supplies the actual
feature computation used by Glue and its unit tests. tests/test_data.py
compares all customers against observation-only recomputation, verifies the
future holdout labels and rejects stale features. Missing datasets fail.

Gap to Level 3: Refresh and recovery still require an operator. Collecting
transaction history into driver memory is adequate for this sample but limits
scale. Event time identifies a generation; it is not an immutable input manifest.

Top priority investment: Deploy the scheduled Step Functions workflow with
quality checks, bounded retries, alerts and an S3-version manifest for each run.

## MLOps Maturity

Current level: 2, automated.

Evidence: models/churn/churn_model.py preserves Lab 3's split and selected
hyperparameters. buildspec.yml enforces tests and evaluation after each push;
pipeline.yaml declares a native CodeBuild failure alarm.
scripts/lab4-lineage.py records the code SHA, data URI, generation timestamp
and evaluation metrics on the model package. docs/lab4-mlflow-runs.txt
exports the retained MLflow App experiments with three different configurations.

Gap to Level 3: Offline gates do not establish production performance,
calibration or fairness over time. Deployment rollback and labeled-production
feedback are not yet implemented.

Top priority investment: Add daily production slice evaluation and the
performance-triggered workflow, retaining the same gates and approval boundary
so a drift event cannot automatically promote an unvalidated model.
