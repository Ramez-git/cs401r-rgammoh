"""Write the Task 1 report from observed outputs, never reference/example scores."""
import json
from pathlib import Path
import pandas as pd
root = Path(__file__).resolve().parents[1]
out = root/'docs/lab3-evidence'
m = json.loads((out/'evaluation_metrics.json').read_text())
meta = json.loads((out/'run-metadata.json').read_text())
experiments = json.loads((out/'experiment-comparison.json').read_text())
slices = pd.read_csv(out/'slice-evaluation.csv')
importance = pd.read_csv(out/'feature-importance.csv', index_col=0).gain.sort_values(ascending=False)
registration = json.loads((out/'registration.json').read_text())
args = meta['arguments']
rows = '\n'.join(f"| {r['name']} | {r['depth']} | {r['eta']} | {r['selected_rounds']} | {r['auc_roc']:.4f} | {r['precision_top10']:.4f} | {r['recall_top10']:.4f} |" for r in experiments)
slice_rows = '\n'.join(f"| {r.tier} | {r.n} | {r.positives} | {r.auc:.4f} | {r.recall:.4f} | {r.too_small} | {r.recall_gap_flag} |" for r in slices.itertuples())
weak_auc = slices.sort_values('auc').iloc[0]
weak_recall = slices.sort_values('recall').iloc[0]
feature_rows = '\n'.join(f'| {name} | {value:.3f} |' for name, value in importance.items())
report = f'''# Lab 3 Task 1: churn evaluation

## Data and provenance

This is an actual run against the restored Lab 2 Feature Store offline table in
`us-east-1`, queried through Athena under the student's IAM identity. The original
Lab 2 pipeline was rerun after its October 2 teardown. It produced the same
synthetic population; [restore log](lab3-data-restore.log) records the jobs and
complete offline verification. Training did not read the feature Parquet path or
a local CSV. Athena query ID: `{meta['athena_query_id']}`.

Features describe purchases through 2026-04-01; `churn_label` means no purchase in
(2026-04-01, 2026-06-30]. Query dates bound ingestion time, not the observation
window. SQL ranks each customer's versions, excludes a latest tombstone, and
orders customers deterministically before splitting. Missing numeric features
remain NaN for XGBoost's native missing-value handling; missing labels, missing
tiers, duplicate IDs and infinite inputs fail explicitly.

The Feature Group contains 13 candidate features. This model uses 11 numeric
features: it excludes the hand-written `churn_risk_score` recency heuristic and
keeps `loyalty_tier` only for slice analysis. IDs, event time and the target are
never predictors. No outcome-window features are constructed.

## Experiment design

XGBoost version: **{meta['xgboost_version']}**. Split seed: **{args['seed']}**.
The stratified outer split reserves **{m['n_val_samples']:,} test customers** and
uses **{m['n_train_samples']:,} for training**. Each development run further
splits that training partition 80/20. Configuration and boosting-round selection
use only the inner validation AUC; the test labels are not used for early
stopping or configuration selection. The selected configuration is refitted on
all outer training rows for **{m['selected_rounds']} rounds**, then evaluated once
on the outer test set. No test-seed search was performed.

All three development runs and the final run are logged to the SageMaker MLflow
**App**, not a Tracking Server. Failed development gates are retained rather than
hidden; the gate is decisive for final registration. These development scores
are inner-validation results and should not be compared as if they were test
scores:

| Experiment | Depth | Learning rate | Selected rounds | Validation AUC | Precision@10% | Recall@10% |
|---|---:|---:|---:|---:|---:|---:|
{rows}

Final run: `{meta['mlflow_run_id']}`. Positive-class weight is the ratio of negative
to positive labels in the fit partition: **{meta['resolved_scale_pos_weight']:.6f}**
for the final training rows. This counteracts the roughly 22% churn prevalence.
It also means scores are useful for ranking but are not demonstrated to be
calibrated probabilities. The baseline uses only `days_since_last_purchase`,
the same training/test customers, and the same class-weight derivation. Its
fixed hyperparameters are recorded in `run-metadata.json`.

## Final held-out results

| Metric | Observed | Requirement |
|---|---:|---|
| AUC-ROC | {m['auc_roc']:.4f} | Report; no absolute threshold |
| Precision @ top 10% | {m['precision_top10']:.4f} | >= 0.50 |
| Recall @ top 10% | {m['recall_top10']:.4f} | >= 0.25 |
| Recency-only AUC | {m['baseline_auc']:.4f} | Trained baseline |
| AUC improvement | {m['auc_vs_baseline']:+.4f} | Positive, with CI |
| 95% CI on improvement | [{m['lift_ci_low']:.4f}, {m['lift_ci_high']:.4f}] | Lower bound > 0 |

The contact budget selects exactly **{m['n_targeted']}** customers, using descending
scores and stable customer-ID order to break ties. Precision is churners among
those contacts; recall is contacted churners divided by all test churners.
The interval uses **{args['bootstrap_n']:,} paired bootstrap resamples**: each
replicate scores both frozen models on exactly the same resampled test rows.
This quantifies uncertainty from the held-out customers, conditional on the
trained models; it does not include uncertainty from retraining or population
drift. A positive lower bound supports additional signal beyond recency.

![Confusion matrix](lab3-evidence/confusion-matrix.png)

The confusion matrix uses the predeclared threshold **{args['threshold']}**, which
is distinct from the top-decile contact budget. Threshold calibration and
business-cost optimization are future work.

## Loyalty-tier slices

Recall uses the **same global top-decile selection** as the aggregate metric;
it is not a separately chosen top decile within each tier. A recall-gap flag
means more than 10 percentage points below overall recall. A slice is marked
too small when n < 100 or either class has fewer than 20 members; this is an
explicit caution rule, not a confidence guarantee for larger slices.

| Tier | n | Churners | AUC | Recall | Too small | Recall-gap flag |
|---|---:|---:|---:|---:|---|---|
{slice_rows}

The weakest ranking slice is **{weak_auc.tier}** (AUC {weak_auc.auc:.4f}); the
lowest contact recall is **{weak_recall.tier}** ({weak_recall.recall:.4f}).
Ranking and contact allocation measure different properties: one global contact
budget can under-serve a tier even when its within-tier ranking is strong.
Any flagged gaps deserve tier-specific error review and a prospective comparison
of contact-allocation policies. Do not change thresholds on these test labels
and then report the same set as independent evidence. Small-sample warnings
above limit conclusions; even adequate sample counts do not establish fairness
or future performance. Platinum has only {int(slices.loc[slices.tier == 'Platinum', 'positives'].iloc[0])} churners, barely
above the predeclared minimum; its high AUC should therefore be interpreted
more cautiously than the larger Bronze and Silver slices.

## What the features contributed

![Feature importance](lab3-evidence/feature-importance.png)

| Feature | Average split gain |
|---|---:|
{feature_rows}

The highest-gain features are **{', '.join(importance.index[:3])}**. The lowest-gain
features are **{', '.join(importance.index[-3:])}**. Gain is descriptive of this
fitted model, not causal attribution; correlated features can share or substitute
for signal. The paired baseline comparison is stronger evidence of the feature
set's collective value than any individual gain ranking. Establishing whether a
low-gain feature is dispensable would require a training-only ablation study.

## Artifacts, registration and checks

Registered package: `{registration['ModelPackageArn']}`.
Approval status: **PendingManualApproval**. The portable JSON model, baseline,
holdout predictions, metrics, plots, SQL execution evidence, MLflow runs and
registry metadata are exported under `docs/lab3-evidence/`. The final numbers
must agree across the report, metrics JSON, MLflow and registry metadata.

Run the checks in [Task 1 verification instructions](lab3-task1-checks.md).
No persistent inference endpoint or SageMaker training job is needed. Full
Lab 3 submission tagging and Tasks 2-4 are separate from this Task 1 result.
'''
(root/'docs/lab3-evaluation-report.md').write_text(report, encoding='utf-8')
print('Wrote docs/lab3-evaluation-report.md from observed evidence')
