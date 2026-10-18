"""Task 1: Athena-backed XGBoost training, honest holdout evaluation and AWS lineage.
Adapted from the CS 401R Lab 3 starter; run --help for parameters.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import tarfile
from datetime import datetime, timezone
import boto3
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import roc_auc_score, confusion_matrix, ConfusionMatrixDisplay
from sklearn.model_selection import train_test_split
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

FEATURE_COLUMNS = ['days_since_last_purchase', 'customer_tenure_days',
    'purchase_frequency_30d', 'purchase_frequency_90d', 'purchase_frequency_180d',
    'avg_order_value', 'total_spend_90d', 'total_lifetime_value', 'avg_basket_size_6m',
    'category_diversity_score', 'online_to_store_ratio']
LABEL_COLUMN = 'churn_label'


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--feature-group-name', required=True)
    p.add_argument('--artifacts-bucket', required=True)
    p.add_argument('--mlflow-arn', required=True)
    p.add_argument('--region', default='us-east-1')
    p.add_argument('--training-start-date', default='2026-01-01')
    p.add_argument('--training-end-date', default='2027-01-01')
    p.add_argument('--max-depth', type=int, default=4)
    p.add_argument('--eta', type=float, default=.1)
    p.add_argument('--num-round', type=int, default=200)
    p.add_argument('--min-child-weight', type=float, default=5)
    p.add_argument('--subsample', type=float, default=.8)
    p.add_argument('--colsample-bytree', type=float, default=.8)
    p.add_argument('--scale-pos-weight', type=float)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--test-size', type=float, default=.30)
    p.add_argument('--validation-size', type=float, default=.20)
    p.add_argument('--early-stopping-rounds', type=int, default=20)
    p.add_argument('--bootstrap-n', type=int, default=2000)
    p.add_argument('--threshold', type=float, default=.5)
    p.add_argument('--nthread', type=int, default=4)
    p.add_argument('--baseline-depth', type=int, default=4)
    p.add_argument('--baseline-eta', type=float, default=.1)
    p.add_argument('--baseline-rounds', type=int, default=200)
    p.add_argument('--baseline-subsample', type=float, default=.9)
    p.add_argument('--baseline-colsample', type=float, default=.9)
    p.add_argument('--mlflow-experiment', default='northstar-churn')
    p.add_argument('--run-name', required=True)
    p.add_argument('--model-dir', default='model')
    p.add_argument('--output-data-dir', default='docs/lab3-evidence')
    p.add_argument('--model-package-group', default='northstar-churn-models')
    p.add_argument('--register', action='store_true')
    p.add_argument('--final', action='store_true', help='Evaluate untouched test set, not inner validation')
    p.add_argument('--fixed-rounds', type=int, help='Selected on inner validation; refit all training rows')
    a = p.parse_args()
    if a.final and not a.fixed_rounds:
        p.error('--final requires --fixed-rounds selected on inner validation')
    if a.register and not a.final:
        p.error('Only the final held-out run can be registered')
    if ':mlflow-app/' not in a.mlflow_arn:
        p.error('Use an MLflow App ARN, never a Tracking Server')
    return a


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, default=str, allow_nan=False), encoding='utf-8')


def load_features(args, session):
    from sagemaker.session import Session
    from sagemaker.feature_store.feature_group import FeatureGroup
    group = FeatureGroup(name=args.feature_group_name, sagemaker_session=Session(boto_session=session))
    query = group.athena_query()
    start, end = [datetime.strptime(v, '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp()
                  for v in (args.training_start_date, args.training_end_date)]
    # Rank tombstones as well: a deleted latest version must not resurrect an older row.
    sql = f'''WITH ranked AS (
      SELECT customer_id, {', '.join(FEATURE_COLUMNS)}, churn_label, loyalty_tier,
             is_deleted, ROW_NUMBER() OVER (PARTITION BY customer_id
             ORDER BY event_time DESC, write_time DESC, api_invocation_time DESC) AS rn
      FROM "{query.table_name}"
      WHERE event_time >= {start} AND event_time < {end}
    ) SELECT customer_id, {', '.join(FEATURE_COLUMNS)}, churn_label, loyalty_tier
      FROM ranked WHERE rn = 1 AND NOT is_deleted ORDER BY customer_id'''
    query.run(query_string=sql, output_location=f's3://{args.artifacts_bucket}/artifacts/athena-results/')
    query.wait()
    qid = query.get_query_execution()['QueryExecution']['QueryExecutionId']
    print(f'Athena QueryExecutionId: {qid}', flush=True)
    df = query.as_dataframe().sort_values('customer_id').reset_index(drop=True)
    if df.empty or df.customer_id.duplicated().any():
        raise ValueError('Feature Store data must contain unique customers and cannot be empty')
    if df.churn_label.isna().any() or not set(df.churn_label.unique()) <= {0, 1}:
        raise ValueError('Labels must be present and binary')
    df[FEATURE_COLUMNS] = df[FEATURE_COLUMNS].apply(pd.to_numeric, errors='raise')
    if np.isinf(df[FEATURE_COLUMNS].to_numpy()).any() or df.loyalty_tier.isna().any():
        raise ValueError('Infinite inputs or missing slice labels')
    return df, qid


def top_mask(scores):
    n = max(1, math.ceil(len(scores) * .10))
    mask = np.zeros(len(scores), dtype=bool)
    mask[np.argsort(-scores, kind='stable')[:n]] = True
    return mask


def bootstrap_lift_ci(y, scores, baseline, n=2000, seed=42):
    rng, diffs = np.random.default_rng(seed), []
    for _ in range(n):
        ix = rng.integers(0, len(y), len(y))
        if np.unique(y[ix]).size == 2:
            diffs.append(roc_auc_score(y[ix], scores[ix]) - roc_auc_score(y[ix], baseline[ix]))
    if len(diffs) < n * .9:
        raise ValueError('Insufficient two-class bootstrap replicates')
    return np.quantile(diffs, [.025, .975]).tolist()


def evaluate(y, scores, baseline, args):
    mask = top_mask(scores)
    low, high = bootstrap_lift_ci(y, scores, baseline, args.bootstrap_n, args.seed)
    auc, base = roc_auc_score(y, scores), roc_auc_score(y, baseline)
    return {k: round(float(v), 4) for k, v in {
        'auc_roc': auc, 'baseline_auc': base, 'auc_vs_baseline': auc-base,
        'precision_top10': y[mask].mean(), 'recall_top10': y[mask].sum()/y.sum(),
        'lift_ci_low': low, 'lift_ci_high': high, 'positive_rate_val': y.mean()
    }.items()} | {'n_val_samples': len(y), 'n_targeted': int(mask.sum())}


def plots_and_slices(model, frame, y, scores, args, out):
    selected = top_mask(scores)
    agg = y[selected].sum()/y.sum()
    rows = []
    for tier in ['Bronze', 'Silver', 'Gold', 'Platinum']:
        m = frame.loyalty_tier.to_numpy() == tier
        n, pos = int(m.sum()), int(y[m].sum())
        recall = float(y[m & selected].sum()/pos) if pos else None
        rows.append({'tier': tier, 'n': n, 'positives': pos,
                     'auc': float(roc_auc_score(y[m], scores[m])) if 0 < pos < n else None,
                     'recall': recall, 'too_small': n < 100 or min(pos, n-pos) < 20,
                     'recall_gap_flag': recall is not None and recall < agg - .10})
    pd.DataFrame(rows).to_csv(out/'slice-evaluation.csv', index=False)
    ConfusionMatrixDisplay(confusion_matrix(y, scores >= args.threshold),
                           display_labels=['Retained', 'Churn']).plot(cmap='Blues')
    partition = 'Test' if args.final else 'Inner-validation'
    plt.title(f'{partition} predictions at probability threshold {args.threshold}')
    plt.tight_layout(); plt.savefig(out/'confusion-matrix.png', dpi=150); plt.close()
    gain = model.get_score(importance_type='gain')
    imp = pd.Series({f: gain.get(f, 0) for f in FEATURE_COLUMNS}).sort_values()
    imp.to_csv(out/'feature-importance.csv', header=['gain'])
    imp.plot.barh(figsize=(9, 6), color='#2563a6')
    plt.xlabel('Average split gain (not causal importance)')
    plt.tight_layout(); plt.savefig(out/'feature-importance.png', dpi=150); plt.close()


def main():
    a = parse_args()
    os.environ['AWS_DEFAULT_REGION'] = a.region
    out, modeldir = Path(a.output_data_dir), Path(a.model_dir)
    out.mkdir(parents=True, exist_ok=True); modeldir.mkdir(parents=True, exist_ok=True)
    session = boto3.Session(region_name=a.region)
    df, qid = load_features(a, session)
    training, test = train_test_split(df, test_size=a.test_size, random_state=a.seed, stratify=df.churn_label)
    if a.final:
        fit, evaluation = training, test
    else:
        fit, evaluation = train_test_split(training, test_size=a.validation_size,
                                          random_state=a.seed, stratify=training.churn_label)
    membership = df[['customer_id']].copy()
    membership['partition'] = np.where(membership.customer_id.isin(test.customer_id), 'test', 'training')
    membership.to_csv(out/'split-membership.csv', index=False)
    assert set(fit.customer_id).isdisjoint(evaluation.customer_id)
    assert set(training.customer_id).isdisjoint(test.customer_id)
    # Canonical order also makes exact top-decile tie handling reproducible.
    fit = fit.sort_values('customer_id'); evaluation = evaluation.sort_values('customer_id')
    y = evaluation.churn_label.to_numpy(dtype=int)
    weight = a.scale_pos_weight if a.scale_pos_weight is not None else float((fit.churn_label == 0).sum()/(fit.churn_label == 1).sum())
    params = dict(objective='binary:logistic', eval_metric=['logloss', 'auc'],
                  max_depth=a.max_depth, eta=a.eta, min_child_weight=a.min_child_weight,
                  subsample=a.subsample, colsample_bytree=a.colsample_bytree,
                  scale_pos_weight=weight, seed=a.seed, nthread=a.nthread)
    print(f'Rows: total={len(df)} training={len(fit)} evaluation={len(evaluation)}', flush=True)
    print('Training XGBoost with params: ' + json.dumps(params), flush=True)
    dfit = xgb.DMatrix(fit[FEATURE_COLUMNS], label=fit.churn_label)
    deval = xgb.DMatrix(evaluation[FEATURE_COLUMNS], label=y)
    if a.final:
        model = xgb.train(params, dfit, num_boost_round=a.fixed_rounds)
        rounds = a.fixed_rounds
    else:
        model = xgb.train(params, dfit, num_boost_round=a.num_round, evals=[(deval, 'validation')],
                          early_stopping_rounds=a.early_stopping_rounds, verbose_eval=25)
        rounds = model.best_iteration + 1
        model = model[:rounds]
    baseline_params = params | dict(max_depth=a.baseline_depth, eta=a.baseline_eta,
                                    subsample=a.baseline_subsample, colsample_bytree=a.baseline_colsample)
    baseline = xgb.train(baseline_params, xgb.DMatrix(fit[['days_since_last_purchase']], label=fit.churn_label),
                         num_boost_round=a.baseline_rounds)
    scores = model.predict(deval)
    base_scores = baseline.predict(xgb.DMatrix(evaluation[['days_since_last_purchase']]))
    metrics = evaluate(y, scores, base_scores, a)
    metrics.update(n_train_samples=len(fit), selected_rounds=rounds)
    passed = metrics['precision_top10'] >= .5 and metrics['recall_top10'] >= .25 and metrics['lift_ci_low'] > 0
    print(json.dumps(metrics, indent=2), flush=True)
    print('Evaluation gates: ' + ('PASS' if passed else 'FAIL'), flush=True)
    model.save_model(modeldir/'model.json')
    baseline.save_model(modeldir/'baseline.json')
    reloaded = xgb.Booster(); reloaded.load_model(modeldir/'model.json')
    np.testing.assert_array_equal(scores, reloaded.predict(deval))
    predictions = evaluation[['customer_id', 'loyalty_tier', 'churn_label'] + FEATURE_COLUMNS].copy()
    predictions['probability'] = scores; predictions['baseline_probability'] = base_scores
    predictions['selected_top10'] = top_mask(scores)
    predictions.to_csv(out/'holdout-predictions.csv', index=False)
    dump(out/'evaluation_metrics.json', metrics)
    plots_and_slices(model, evaluation, y, scores, a, out)
    metadata = {'feature_columns': FEATURE_COLUMNS, 'xgboost_version': xgb.__version__,
                'arguments': vars(a), 'resolved_scale_pos_weight': weight, 'params': params,
                'baseline_params': baseline_params, 'evaluation_metrics': metrics,
                'athena_query_id': qid, 'evaluation_split': 'test' if a.final else 'inner_validation',
                'data_sha256': hashlib.sha256(df.to_csv(index=False).encode()).hexdigest(),
                'trained_at': datetime.now(timezone.utc).isoformat()}
    import mlflow
    mlflow.set_tracking_uri(a.mlflow_arn); mlflow.set_experiment(a.mlflow_experiment)
    with mlflow.start_run(run_name=a.run_name) as run:
        mlflow.log_params({k: v for k, v in vars(a).items() if v is not None} | {
            'scale_pos_weight': weight, 'xgboost_version': xgb.__version__, 'selected_rounds': rounds,
            'evaluation_split': metadata['evaluation_split'], 'data_sha256': metadata['data_sha256']})
        mlflow.log_metrics(metrics)
        mlflow.set_tag('athena_query_id', qid)
        metadata['mlflow_run_id'] = run.info.run_id
        dump(modeldir/'model_metadata.json', metadata)
        mlflow.log_artifacts(str(modeldir), artifact_path='model')
        mlflow.log_artifact(str(out/'evaluation_metrics.json'))
    dump(out/'run-metadata.json', metadata)
    import shutil
    shutil.copyfile(modeldir/'model.json', out/'model.json')
    shutil.copyfile(modeldir/'baseline.json', out/'baseline.json')
    print('MLflow run ID: ' + metadata['mlflow_run_id'], flush=True)
    if a.register:
        if not passed:
            raise ValueError('Final evaluation failed; refusing registration')
        sm = session.client('sagemaker')
        try:
            sm.describe_model_package_group(ModelPackageGroupName=a.model_package_group)
        except sm.exceptions.ClientError as e:
            if e.response['Error']['Code'] not in ['ValidationException', 'ResourceNotFound']:
                raise
            sm.create_model_package_group(ModelPackageGroupName=a.model_package_group,
                                         ModelPackageGroupDescription='NorthStar churn models')
        # XGBoost JSON is portable across versions; include a custom inference loader.
        code = modeldir/'code'; code.mkdir(exist_ok=True)
        import shutil
        shutil.copyfile('models/churn/inference.py', code/'inference.py')
        archive = modeldir/'model.tar.gz'
        with tarfile.open(archive, 'w:gz') as tar:
            for name in ['model.json', 'model_metadata.json', 'code/inference.py']:
                tar.add(modeldir/name, arcname=name)
        key = f'artifacts/churn/{metadata["mlflow_run_id"]}/model.tar.gz'
        session.client('s3').upload_file(str(archive), a.artifacts_bucket, key)
        from sagemaker import image_uris
        image = image_uris.retrieve('xgboost', region=a.region, version='1.7-1', image_scope='inference', instance_type='ml.m5.large')
        response = sm.create_model_package(ModelPackageGroupName=a.model_package_group,
            ModelPackageDescription=f'XGBoost {xgb.__version__}; Athena {qid}; final held-out evaluation',
            ModelApprovalStatus='PendingManualApproval',
            InferenceSpecification={'Containers': [{'Image': image,
                'ModelDataUrl': f's3://{a.artifacts_bucket}/{key}',
                'Environment': {'SAGEMAKER_PROGRAM': 'inference.py', 'SAGEMAKER_SUBMIT_DIRECTORY': '/opt/ml/model/code'}}],
                'SupportedContentTypes': ['application/json'], 'SupportedResponseMIMETypes': ['application/json'],
                'SupportedRealtimeInferenceInstanceTypes': ['ml.m5.large'],
                'SupportedTransformInstanceTypes': ['ml.m5.large']},
            CustomerMetadataProperties={k: str(v) for k, v in metrics.items()} | {
                'mlflow_run_id': metadata['mlflow_run_id'], 'athena_query_id': qid,
                'xgboost_version': xgb.__version__})
        dump(out/'registration.json', response)
        print('Registered PendingManualApproval: ' + response['ModelPackageArn'], flush=True)
    print('Training complete.', flush=True)

if __name__ == '__main__':
    main()
