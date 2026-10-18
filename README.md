# NorthStar - CS 401R

Lab 1 provisions the platform foundation. Lab 2 adds private networking, data
engineering permissions, retention policies, and a reproducible customer-feature
pipeline for Lab 3 churn modeling.

## Architecture

![Data lineage](docs/lab2-data-lineage.png)

Terraform lives in `infrastructure/`. Modules:

- `vpc`: public subnet, internet gateway, NAT gateway, private subnet and routes.
- `storage`: private encrypted versioned S3 data bucket and five lifecycle rules.
- `iam`: MLEngineer, DataEngineer, ModelMonitor and their scoped permissions.
- `sagemaker`: VPC-only Studio domain and MLEngineer profile in the private subnet.
- `glue`: catalog, raw crawler, private NETWORK connection, worker security group,
  uploaded scripts, and two Glue 4.0 Spark jobs (two G.1X workers each).
- `feature_store`: 16-field customer feature group with online and offline stores.

DataEngineer reads/writes raw, processed and features; it can only read job scripts
under artifacts/glue. ModelMonitor reads artifacts and publishes monitoring data;
it cannot write S3 or start processing jobs. MLEngineer retains Lab 1 permissions
and gains feature-record read access.

## Prerequisites

Terraform >= 1.5, AWS CLI authenticated to the lab account in us-east-1, Python
with boto3, pandas and pyarrow, and Git Bash/WSL for the supplied shell scripts.
Docker is needed for LocalStack only. Do not commit credentials, `.env`,
`*.tfvars`, Terraform state, or saved plans. The backend bucket and lock table
from Lab 1 must already exist; see `scripts/bootstrap-state.sh` for initial setup.

## Deploy

Run from the repository root:

```bash
terraform -chdir=infrastructure/environments/dev init
terraform fmt -check -recursive infrastructure
terraform -chdir=infrastructure/environments/dev validate
terraform -chdir=infrastructure/environments/dev plan -out=lab2.tfplan
terraform -chdir=infrastructure/environments/dev apply lab2.tfplan 2>&1 | tee docs/lab2-extend-output.txt
```

Review the plan first. If Lab 1 still runs, moving the domain can replace it.
The dev bucket enables force_destroy for regenerable synthetic data; deleting
the stack can delete every object version. The NAT gateway incurs ongoing cost.

## Run the pipeline

```bash
python scripts/run-lab2.py 2>&1 | tee docs/lab2-pipeline-output.txt
python scripts/verify-offline-lab2.py 2>&1 | tee docs/lab2-offline-verification.txt
```

The runner uploads the supplied CSV, starts and waits for the crawler, verifies
`northstar_dev.customers`, runs transform then feature-engineer, checks online
GetRecord, and waits for Feature Store offline Parquet delivery. Each stage fails
explicitly on errors or timeout. Do not launch overlapping pipeline runs: outputs
are overwritten in place. The runner supports `--project`, `--environment`, and
`--region` to match Terraform settings.
The offline verifier waits for every customer in the current snapshot and compares
all stored feature values against the feature-job output, not just file existence.

The transform trims fields, parses both date formats, imputes numeric medians and
unknown strings, and deterministically deduplicates transaction IDs. Quality gates
run before writing Parquet. See [the data contract](docs/lab2-data-contract.md).

Features use history through 2026-04-01; the churn label uses only purchases after
that cutoff through 2026-06-30. This is a temporal observation/outcome split, not
a train/test split. Customers without pre-cutoff history are excluded. Rolling
N-day windows are `(T - N days, T]`. The baseline risk score increases linearly
with recency in each band, with the high band saturating at 180 days.

The feature job writes `features/customers/`. Feature Store manages its separate
`features/offline-store/` prefix. Offline delivery is asynchronous; a successful
Glue run alone is insufficient proof that offline records have arrived.

## Validation

```bash
# Local Spark data tests (pyspark 3.5.x and Java 8/11/17)
python scripts/test-lab2-local.py

# Local infrastructure; NAT and lifecycle deliberately disabled
make local-validate LOCAL_OUT=docs/lab2-localstack-output.txt

# Actual deployed AWS resources and output data
export AWS_DEFAULT_REGION=us-east-1
bash scripts/verify-lab2.sh 2>&1 | tee docs/lab2-verify-output.txt
bash scripts/check-secrets.sh
```

Windows PowerShell users can run `./scripts/validate-local.ps1` instead of make.
It invokes the AWS CLI against localhost with temporary dummy credentials and
restores the caller's environment. Use PowerShell's `Tee-Object` for log capture.
Git Bash must resolve `python3` to a real Python installation with pandas/pyarrow,
not the Windows Store alias.
The supplied verifier has one portability fix: its Python tally file uses LF
line endings so Git Bash can read numeric counts on Windows. All checks are kept.

Local tests execute the production Spark functions without Glue-only imports.
They cover whitespace, nulls, both date formats, median imputation, deduplication,
cutoff boundaries, future leakage, empty recent history, loyalty thresholds and
the complete sample. AWS jobs provide validation on the actual Glue 4.0 runtime.

## Submission and teardown

Review the changes and verification evidence, commit, push the branch, then tag
the intended grading commit:

```bash
git tag lab2-submit
git push origin lab2-submit
```

Submit the existing repository URL in Canvas. After capturing evidence and
submitting, review and run `scripts/teardown-lab2.sh`, capturing its actual output
in `docs/lab2-destroy-output.txt`. The supplied script deletes synthetic data and
cleans up service-created resources outside Terraform; inspect its scope before
using it in an account shared with other projects. Do not delete the remote-state
backend. Commit teardown evidence as the guide requires; do not silently move an
already submitted tag.

## Lab 3 Task 1: churn prediction

Task 1 uses the existing Lab 2 Feature Store via Athena, trains XGBoost locally,
logs three distinct development experiments plus the final run to a SageMaker
MLflow **App**, and registers a passing final model as `PendingManualApproval`.
Bucket, Feature Group and role names come from the existing Terraform outputs.
No persistent endpoint or SageMaker training job is required.

Development selects hyperparameters and boosting rounds on an inner validation
split; the stratified 30% outer test set is reserved for the final run. Features
exclude identifiers, the target and the hand-coded recency risk score. Numeric
missing values use XGBoost's native handling. Evaluation includes exact-budget
top-decile precision/recall, a trained recency-only baseline, 2,000 paired
bootstrap replicates, and loyalty-tier slices with counts and caution flags.

```powershell
python -m venv .venv-lab3
./.venv-lab3/Scripts/python.exe -m pip install -r requirements-lab3-task1.txt
./.venv-lab3/Scripts/python.exe -u scripts/run-lab3-task1.py
./.venv-lab3/Scripts/python.exe scripts/collect-lab3-task1.py
./.venv-lab3/Scripts/python.exe scripts/write-lab3-task1-report.py
./.venv-lab3/Scripts/python.exe scripts/verify-lab3-task1.py --live
```

For verification of saved results without AWS, omit `--live`. Detailed steps:
[Task 1 checks](docs/lab3-task1-checks.md). Findings and plots:
[evaluation report](docs/lab3-evaluation-report.md). Models, test predictions,
metrics, final log and AWS evidence: `docs/lab3-evidence/`. Transient training
artifacts live in ignored `model/`.

The full supplied evidence collector still checks Tasks 2-4. The separate
`collect-lab3-task1.py` invokes its AWS export functions for Task 1 only; passing
that check does not claim the rest of Lab 3 is complete. Do not create or move
the final `lab3-submit` tag until the remaining tasks and teardown are complete.

## Lab 3 Tasks 2-4: Track B retention offers and submission evidence

Selected tracks: **A + B**. The RAG system embeds the four supplied policy
sources with Titan V2 and retrieves from a local FAISS index. It compares
tier-only, constraint-only and hybrid retrieval. Haiku 4.5 drafts structured
category copy; a renderer adds incentives parsed from retrieved policy and
explicit eligibility conditions. All five demonstrated customer profiles come
from the churn model's actual top-decile predictions, with categories drawn
from pre-cutoff transactions.

The original free-form failures are preserved. Final evaluation runs all four
supplied RAGAS cases three times; per-case scores, mean and range, before/after
results and judge traces are saved. The October 12 guide update makes these
numeric scores diagnostic rather than grading thresholds. The conditional
pipeline improves safety while reducing measured answer relevance; the report
explains that tradeoff rather than hiding it.

Track B requires **Python 3.12** and its own environment because a RAGAS dependency
has no Windows Python 3.14 wheel:

```powershell
py -3.12 -m venv .venv-lab3-rag312
./.venv-lab3-rag312/Scripts/python.exe -m pip install -r requirements-lab3-track-b.txt
./.venv-lab3-rag312/Scripts/python.exe -m ipykernel install --user --name northstar-lab3-rag --display-name 'NorthStar Lab 3 (Python 3.12)'
./.venv-lab3-rag312/Scripts/python.exe scripts/verify-lab3-track-b.py
# Live Bedrock end-to-end demo; saved outputs are already included
./.venv-lab3-rag312/Scripts/python.exe scripts/build-lab3-demo.py
```

Read [complete checks and setup](docs/lab3-checks.md),
[Track B evaluation](docs/lab3-track-b-report.md),
[design justification](docs/lab3-model-design.md), and
[the executed notebook](notebooks/lab3-demo.ipynb).

The [detailed manual review](docs/lab3-manual-review.md) records inspection scope,
fixes and remaining limitations. Run `scripts/audit-lab3-evidence.py` with the
Track B Python environment for full-file and numerical evidence reconciliation.

Prompts: `prompt_templates/final_offer_system.md`; corpus:
`northstar-policy-docs/`; implementation: `rag/offer_pipeline.py`.
The two dependency lock files preserve the separate working Task 1 and Track B
stacks. `scripts/run-lab3-track-b.py` reuses completed frozen evaluation evidence;
new experiments should have distinct names. The local vector/embedding cache is
ignored by Git and rebuilt from policy text when needed.

Before submission, export account-side evidence and run teardown:

```powershell
$env:PYTHON_BIN='./.venv-lab3/Scripts/python.exe'
$env:PYTHONUTF8='1'
$env:AWS_DEFAULT_REGION='us-east-1'
& 'C:/Program Files/Git/bin/bash.exe' scripts/collect-lab3-evidence.sh --track B
& 'C:/Program Files/Git/bin/bash.exe' scripts/teardown-lab3.sh
```

Commit code and all `docs/`/`notebooks/` evidence, tag the reviewed commit
`lab3-submit`, push the branch and tag, and submit the repository URL in Canvas.
Never commit credentials, `.env`, Terraform state or `.tfvars`. The data bucket,
Feature Store, MLflow App and registry are retained; temporary restoration
networking and Glue resources have been removed. No persistent endpoint,
Tracking Server, AgentCore stack or hosted vector database is needed.
