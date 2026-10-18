# Check Lab 3 Task 1

Open PowerShell in `C:\Users\Administrator\Documents\CS 401R\cs401r-rgammoh`.

## Verify the completed result locally

```powershell
./.venv-lab3/Scripts/python.exe scripts/verify-lab3-task1.py
```

Expected final line: `TASK 1 VERIFICATION PASSED`. This reloads the committed
JSON models, predicts every saved test customer, recomputes the metrics and
2,000 paired bootstrap replicates, and checks exported MLflow/registry evidence.
It also exercises the JSON inference handler. It does not train or call a model
endpoint and requires no AWS login.

For a fresh clone, first create the environment:

```powershell
python -m venv .venv-lab3
./.venv-lab3/Scripts/python.exe -m pip install -r requirements-lab3-task1.txt
```

The captured environment uses Python 3.14 on Windows. The lock file records the
exact versions used; other platforms may need equivalent compatible versions.

## Confirm the records still exist in AWS

```powershell
./.venv-lab3/Scripts/python.exe scripts/verify-lab3-task1.py --live
```

This additionally checks the real Athena query succeeded, the final MLflow run
matches, and the registered package is complete and PendingManualApproval.
It requires your existing AWS credentials. It does not deploy an endpoint.

In the AWS console, choose **us-east-1**:

- SageMaker: open MLflow Apps, `northstar-mlflow`, experiment `northstar-churn`.
  Look for three development configurations and the final run. Use the App's
  launch action to open MLflow.
- SageMaker Model Registry: open `northstar-churn-models`, inspect the final
  version, approval status and customer metadata metrics.
- Athena: find the query ID recorded in `docs/lab3-evidence/train-final.log`.
  Its SQL reads the Feature Store table and ends with customer-ID ordering.

## Inspect the outputs

Read `docs/lab3-evaluation-report.md` for metrics, the baseline comparison,
experiment results, slice analysis, and plots. See `docs/lab3-evidence/` for the
underlying results. `holdout-predictions.csv` is synthetic coursework data and
allows independent scoring without AWS.

## Rerun training (uses AWS)

```powershell
./.venv-lab3/Scripts/python.exe -u scripts/run-lab3-task1.py
./.venv-lab3/Scripts/python.exe scripts/collect-lab3-task1.py
./.venv-lab3/Scripts/python.exe scripts/write-lab3-task1-report.py
./.venv-lab3/Scripts/python.exe scripts/verify-lab3-task1.py --live
```

The runner reads bucket, role and Feature Group names from the existing Terraform
outputs, queries Athena for each run, compares the same three predeclared
configurations on inner validation data, and registers a new final version only
if all gates pass. Rerunning writes new evidence, MLflow runs and a registry
version. It needs the Feature Store, bucket, IAM roles and MLflow App retained.
It does not need the Glue pipeline or VPC once the data is in the offline store.

Focused evaluation tests:

```powershell
./.venv-lab3/Scripts/python.exe scripts/test-lab3-task1.py
```

## Resource state after Task 1

The temporary Glue jobs/crawler and VPC/NAT resources used to restore the Lab 2
snapshot were removed after successful ingestion. The data bucket, Feature
Store, existing IAM roles, registry model and MLflow App remain. No endpoints,
active SageMaker jobs, MLflow Tracking Servers, NAT gateways or allocated Elastic
IPs were left running. Storage and future API calls can still incur usage costs.

This was a targeted recovery and cleanup using the existing Terraform root;
a full future `terraform apply` will propose recreating the removed Lab 2
network/Glue/Studio resources. That is not needed to rerun Task 1 against the
retained offline data. See `lab3-network-cleanup-output.txt` and
`lab3-teardown-output.txt` for cleanup evidence.
