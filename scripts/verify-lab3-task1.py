"""Recompute Task 1 metrics from the saved model; optional live AWS consistency check."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import xgboost as xgb
from churn_training_skeleton import FEATURE_COLUMNS, evaluate, top_mask

p = argparse.ArgumentParser()
p.add_argument('--live', action='store_true')
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
out = root/'docs/lab3-evidence'
metadata = json.loads((out/'run-metadata.json').read_text())
metrics = json.loads((out/'evaluation_metrics.json').read_text())
frame = pd.read_csv(out/'holdout-predictions.csv')
model = xgb.Booster(); model.load_model(out/'model.json')
baseline = xgb.Booster(); baseline.load_model(out/'baseline.json')
scores = model.predict(xgb.DMatrix(frame[FEATURE_COLUMNS]))
bases = baseline.predict(xgb.DMatrix(frame[['days_since_last_purchase']]))
np.testing.assert_allclose(scores, frame.probability, atol=1e-7, rtol=0)
np.testing.assert_allclose(bases, frame.baseline_probability, atol=1e-7, rtol=0)
assert frame.customer_id.is_unique
split = pd.read_csv(out/'split-membership.csv')
assert split.customer_id.is_unique
assert set(split.loc[split.partition == 'test', 'customer_id']) == set(frame.customer_id)
assert int((split.partition == 'training').sum()) == metrics['n_train_samples']
assert set(model.feature_names) == set(FEATURE_COLUMNS)
print(f'PASS: saved models reproduce all {len(frame)} holdout predictions')
args = argparse.Namespace(**metadata['arguments'])
computed = evaluate(frame.churn_label.to_numpy(dtype=int), scores, bases, args)
for key, value in computed.items():
    assert abs(value-metrics[key]) < 1e-6, (key, value, metrics[key])
assert metrics['precision_top10'] >= .50 and metrics['recall_top10'] >= .25 and metrics['lift_ci_low'] > 0
print('PASS: recomputed metrics, bootstrap confidence interval and all grading gates')
runs = pd.read_csv(out/'mlflow-runs.csv')
match = runs[runs.run_id == metadata['mlflow_run_id']]
assert len(match) == 1
versions = json.loads((out/'model-registry.json').read_text())['Versions']
package = next(v for v in versions if (v.get('CustomerMetadataProperties') or {}).get('mlflow_run_id') == metadata['mlflow_run_id'])
assert package['ModelApprovalStatus'] == 'PendingManualApproval'
for key in ['auc_roc', 'precision_top10', 'recall_top10', 'baseline_auc', 'lift_ci_low', 'lift_ci_high']:
    assert abs(float(match.iloc[0]['metrics.'+key])-metrics[key]) < 1e-6
    assert abs(float(package['CustomerMetadataProperties'][key])-metrics[key]) < 1e-6
assert len(runs[runs.status == 'FINISHED']) >= 3
print('PASS: MLflow and PendingManualApproval registry evidence match the final model')
slices = pd.read_csv(out/'slice-evaluation.csv')
assert slices.n.sum() == len(frame) and slices.positives.sum() == frame.churn_label.sum()
assert set(slices.tier) == set(frame.loyalty_tier)
print('PASS: loyalty-tier counts reconcile with the held-out customers')
from models.churn.inference import model_fn, input_fn, predict_fn, output_fn
loaded = model_fn(out)
body = frame[FEATURE_COLUMNS].head(3).to_json(orient='records')
result = json.loads(output_fn(predict_fn(input_fn(body, 'application/json'), loaded), 'application/json'))
np.testing.assert_allclose(result['churn_probabilities'], scores[:3], atol=1e-7)
print('PASS: inference handler returns matching churn probabilities')
if a.live:
    import boto3
    import mlflow
    sm = boto3.client('sagemaker', region_name=args.region)
    live = sm.describe_model_package(ModelPackageName=package['ModelPackageArn'])
    assert live['ModelApprovalStatus'] == 'PendingManualApproval'
    assert live['ModelPackageStatus'] == 'Completed', live['ModelPackageStatus']
    import io, tarfile, hashlib
    from urllib.parse import urlparse
    uri = urlparse(live['InferenceSpecification']['Containers'][0]['ModelDataUrl'])
    archive = boto3.client('s3', region_name=args.region).get_object(Bucket=uri.netloc, Key=uri.path.lstrip('/'))['Body'].read()
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
        registered_model = tar.extractfile('model.json').read()
    assert hashlib.sha256(registered_model).digest() == hashlib.sha256((out/'model.json').read_bytes()).digest()
    print('PASS: registered S3 model artifact is identical to the evaluated local model')
    mlflow.set_tracking_uri(args.mlflow_arn)
    run = mlflow.get_run(metadata['mlflow_run_id'])
    for key in ['auc_roc', 'precision_top10', 'recall_top10']:
        assert abs(run.data.metrics[key]-metrics[key]) < 1e-6
        assert abs(float(live['CustomerMetadataProperties'][key])-metrics[key]) < 1e-6
    query = boto3.client('athena', region_name=args.region).get_query_execution(QueryExecutionId=metadata['athena_query_id'])
    assert query['QueryExecution']['Status']['State'] == 'SUCCEEDED'
    print('PASS: live AWS registry, MLflow and Athena agree with the saved evidence')
print('TASK 1 VERIFICATION PASSED')
