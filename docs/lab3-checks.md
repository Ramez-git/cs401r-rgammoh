# Check the completed Lab 3

Repository: `C:\Users\Administrator\Documents\CS 401R\cs401r-rgammoh`.
The selected tracks are A + B. Run all commands from that directory.

## Verify saved results without AWS calls

```powershell
./.venv-lab3/Scripts/python.exe scripts/verify-lab3-task1.py
./.venv-lab3-rag312/Scripts/python.exe scripts/verify-lab3-track-b.py
./.venv-lab3-rag312/Scripts/python.exe scripts/audit-lab3-evidence.py
```

Expected final lines are `TASK 1 VERIFICATION PASSED` and
`TRACK B ARTIFACT VERIFICATION PASSED`. These recalculate the churn metrics and
check saved models, evidence consistency, all repeated RAG evaluations, policy
chunk IDs, the five real high-risk profiles, safety cases, and the clean notebook.
Low RAGAS scores are reported results, not failed grading thresholds under the
October 12 guide update. Read `lab3-track-b-report.md` for the detailed limits.

## Inspect the work

- `notebooks/lab3-demo.ipynb`: eight code cells executed consecutively in a fresh
  kernel, with live Bedrock offers and complete saved outputs.
- `docs/lab3-evaluation-report.md`: churn metrics, baseline, confidence interval,
  tier slices and plots.
- `docs/lab3-track-b-report.md`: retrieval comparison, before/after results,
  judge traces, policy corrections and limitations.
- `docs/lab3-model-design.md`: approximately 700-word design justification.
- `docs/lab3-evidence/track-b-examples.md`: five actual high-risk examples and two
  observed free-form failures, with retrieved chunk IDs and concrete fixes.
- `docs/lab3-evidence/rag_eval.csv`: all four cases in three final judge runs.
- `docs/lab3-evidence/collect-output.txt`: complete supplied collector report.
- `docs/lab3-teardown-output.txt`: final AWS cleanup checks.

## Live verification and demonstration

Your existing AWS credentials are required. These commands incur small per-call
usage charges, with no persistent endpoint:

```powershell
./.venv-lab3/Scripts/python.exe scripts/verify-lab3-task1.py --live
./.venv-lab3-rag312/Scripts/python.exe scripts/verify-bedrock-access.py
./.venv-lab3-rag312/Scripts/python.exe scripts/build-lab3-demo.py
```

You can also select **NorthStar Lab 3 (Python 3.12)** in Jupyter, restart the
kernel and run every cell. Save it with outputs. The demo really scores saved
customers and calls Bedrock; it displays the saved repeated evaluation results
rather than spending on a new judge run every time.

`run-lab3-track-b.py` reuses completed finite evaluation files and frozen offers
for reproducibility. Its files preserve the baseline, intermediate profile-only
experiment, and final structured/rendered pipeline. New model/prompt experiments
should use distinct output names; do not silently overwrite the graded evidence.

## Environment setup on a fresh clone

Task 1 was run in Python 3.14; Track B uses Python 3.12 because a RAGAS dependency
has no Python 3.14 Windows wheel. The two environments keep the working training
stack independent of the RAGAS/LangChain pins. Install Python 3.12 and 3.14 and use:

```powershell
py -3.14 -m venv .venv-lab3
./.venv-lab3/Scripts/python.exe -m pip install -r requirements-lab3-task1.txt
py -3.12 -m venv .venv-lab3-rag312
./.venv-lab3-rag312/Scripts/python.exe -m pip install -r requirements-lab3-track-b.txt
./.venv-lab3-rag312/Scripts/python.exe -m ipykernel install --user --name northstar-lab3-rag --display-name 'NorthStar Lab 3 (Python 3.12)'
```

For offline grading the saved notebook already includes its outputs. The local
FAISS cache is regenerated from corpus text; it is ignored by Git.

## Evidence collection and cleanup

PowerShell with Git Bash installed:

```powershell
$env:PYTHON_BIN='./.venv-lab3/Scripts/python.exe'
$env:PYTHONUTF8='1'
$env:AWS_DEFAULT_REGION='us-east-1'
& 'C:/Program Files/Git/bin/bash.exe' scripts/collect-lab3-evidence.sh --track B
& 'C:/Program Files/Git/bin/bash.exe' scripts/teardown-lab3.sh
```

On Linux/macOS use an environment with the Task 1 dependencies and run the same
supplied shell scripts normally (`PYTHON_BIN=python` if needed).

The data bucket, Feature Store, IAM roles, MLflow App and model records remain
available. Temporary Glue and VPC/NAT resources used for restoring Lab 2 were
removed. A full Terraform apply would propose restoring those old resources;
it is unnecessary for this demo. No inference endpoint, tracking server,
AgentCore stack or hosted vector store is left running.
