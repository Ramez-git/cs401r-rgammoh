# Lab 4 execution

Use AWS account 701145280839 in us-east-1 and the existing cs401r-rgammoh repository.
The Lab 1–3 submission tags remain unchanged.

## Local checks

Install requirements.txt in an isolated Python environment. Download raw,
processed and feature data from the corresponding prefixes in
s3://northstar-dev-data-701145280839. The default test paths are
data/northstar-raw-sample.csv, data/processed/ and data/features/.
Run the deployed Glue feature job first if event_time is older than 48 hours.

Run models/churn/train_sagemaker.py with --train-channel data/features,
--model-dir pointing to an ignored output directory and --output-data-dir
pointing to a separate ignored directory. Copy model_metadata.json from the
output directory beside xgboost-model. Run pytest tests/ with --model-path and
--eval-metrics-path pointing to those real outputs. A bootstrap run may skip
only the champion comparison when no Approved package exists.

The feature functions use an exclusive lower window boundary and inclusive
cutoff. Empty history receives recency 999 and zero counts, spending and
behavioral features. The Glue job calls the same feature module through
--extra-py-files. Whole-dataset reconciliation checks every numeric feature
against the stored output with a tolerance for four-decimal Spark rounding.

## Deployment and demonstration

Restore the VPC, Glue and IAM resources with Terraform. The SageMaker Studio
domain is unnecessary for CI. Check the plan before apply and wait for all
network routes before running Glue. The MLEngineer role must pass itself to
SageMaker; the DataEngineer role needs the scoped S3 folder-marker keys used
by Glue.

Authorize northstar-github through AWS CodeConnections. Deploy pipeline.yaml
as northstar-cicd with GitHubOwner=Ramez-git, GitHubRepo=cs401r-rgammoh,
GitHubBranch=main, and CAPABILITY_NAMED_IAM. Supply the authorized connection
ARN, the MLEngineer role ARN and the separate versioned
northstar-dev-cicd-artifacts-701145280839 bucket. Push implementation before
deployment because stack creation starts a run.

Confirm an email subscription to northstar-model-approvals. After a green
build, approve that package as the champion. Capture BEFORE using
scripts/lab4-evidence.py snapshot. Commit and push a deliberately failing test;
wait for PRE_BUILD failure and the alarm's transition from OK to ALARM.
Capture AFTER FAILED RUN and the full failed log, and save the delivered alarm
email with its received time. Revert the failing commit and push. After the
green build and alarm recovery, capture AFTER REVERT.

The evidence script's capture command accepts --green, --failed and
--package-arn. It saves the full logs, execution histories, registry summary
and package description. Read these files before teardown. The final green
log must contain a passing champion comparison and the fairness warning.

## Teardown and submission

Capture and verify all evidence first. Delete the northstar-cicd stack before
the final documentation push so that push cannot start another training job.
Remove its disposable stage-artifact bucket and build log group only after
the logs have been saved. Remove the temporary Glue/network resources while
retaining the existing data bucket, Feature Store, MLflow App and registry
needed by later labs.

Commit the evidence, verify a fresh clone and scan history for credentials.
Create and push lab4-submit at the final reviewed commit. Submit the repository
URL in Canvas; the grading tag is lab4-submit.
