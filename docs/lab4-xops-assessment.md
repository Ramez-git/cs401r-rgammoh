# NorthStar XOps assessment

## Pipeline Stage Mapping

CodePipeline reuses AWS IAM, logging and storage. Source receives GitHub main
pushes. CodeBuild PRE_BUILD owns Test: data and feature checks. BUILD packages
the commit, runs SageMaker Spot training, evaluates quality, then registers a
passing candidate as PendingManualApproval. Artifact, champion and fairness
tests follow; POST_BUILD rejects candidates whose later gates fail.
ManualApproval owns promotion review. This implements
Source → Test → Build → Evaluate → Register.

## Champion-Challenger

The champion is the newest Approved package. Eligibility requires precision@10%
≥ 0.50, recall@10% ≥ 0.25, a positive lower bound on the paired-bootstrap 95%
AUC-lift interval against the recency baseline, and candidate AUC ≥ champion
AUC − 0.02. Only bootstrap comparison can skip. A loyalty-tier recall gap
above 0.10 flags review without blocking. Promotion remains a separate decision.

## Retraining Triggers

Designed, not deployed: EventBridge Scheduler invokes Step Functions weekly at
cron(0 8 ? * MON *) UTC to refresh Glue features, wait for success and start
CodePipeline. A daily production evaluation publishes NorthStar/Model AUC;
CloudWatch and EventBridge invoke that workflow when AUC < 0.70 for two daily
periods, each with ≥1,000 labeled customers and ≥100 positives.
Insufficient labels alert without retraining.

## DataOps Maturity

Current level: 1, Repeatable, using Chapter 23, section 23.11.1, Table 23.3.

Evidence: infrastructure/modules/ provisions the platform. Glue calls the same
data/feature_engineering.py functions exercised by unit tests.
docs/lab4-build-green.log records 29 data and 22 feature tests passing,
including transaction grain, complete observation-window reconciliation, future
holdout labels and feature freshness below 48 hours. However, the refresh in
docs/lab4-data-refresh.log was operator-triggered. Automatic validation of existing
data does not make ingestion and feature refresh automatically triggered.

Gap to Level 2: Data refresh and recovery need automatic triggers and systematic
freshness/failure monitoring. The weekly workflow above remains a design.

Top priority investment: Deploy the scheduled Step Functions workflow with
bounded retries, quality gates, freshness alarms and an S3-version manifest
per generation.

## MLOps Maturity

Current level: 2, Automated, for the demonstrated model-build lifecycle,
using Table 23.3.

Evidence: docs/lab4-build-green.log records all 72 tests passing without skips,
AUC 0.7846 versus champion v2's 0.7846, and the 31.4-percentage-point fairness
warning. docs/lab4-pipeline-runs.txt proves automatic push triggers.
The native alarm monitors every build. docs/lab4-failure-demo.txt shows PRE_BUILD failure, unchanged registry,
ALARM with successful SNS action, then recovery and new pending package v3.
docs/lab4-model-package.json links code, data timestamp/URI and metrics;
docs/lab4-mlflow-runs.txt contains three differing configurations plus the final
Lab 3 run.

Gap to Level 3, Governed: Registry lineage and quality gates provide partial
governance, but drift-triggered retraining and production feedback are absent.
Saved offline evidence does not establish continuing production quality.

Top priority investment: Implement daily production slice evaluation and the
performance-triggered workflow with auditable decisions, retaining all quality
gates and promotion review.
