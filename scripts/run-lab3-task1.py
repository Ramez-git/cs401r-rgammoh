"""Run the reproducible Task 1 experiments and final model from Terraform outputs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import boto3

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
os.environ['PYTHONUTF8'] = '1'
os.environ['PYTHONUNBUFFERED'] = '1'
OUT = ROOT/'docs/lab3-evidence'
OUT.mkdir(parents=True, exist_ok=True)
config = json.loads(subprocess.check_output(['terraform', '-chdir=infrastructure/environments/dev', 'output', '-json']))
bucket = config['s3_bucket_name']['value']
role = config['ml_engineer_role_arn']['value']
group = config['feature_group_name']['value']
sm = boto3.client('sagemaker', region_name='us-east-1')
apps = sm.list_mlflow_apps().get('Summaries', [])
app = next((v for v in apps if v['Name'] == 'northstar-mlflow'), None)
if app:
    arn = app['Arn']
else:
    arn = sm.create_mlflow_app(Name='northstar-mlflow', ArtifactStoreUri=f's3://{bucket}/artifacts/mlflow/', RoleArn=role)['Arn']
print('MLflow App: ' + arn, flush=True)
for _ in range(60):
    state = sm.describe_mlflow_app(Arn=arn)
    print('MLflow App status: ' + state['Status'], flush=True)
    if state['Status'] == 'Created':
        break
    if state['Status'] in ['CreateFailed', 'Failed']:
        raise RuntimeError(state)
    time.sleep(15)
else:
    raise TimeoutError('MLflow App creation exceeded 15 minutes')
(OUT/'terraform-config.json').write_text(json.dumps({'bucket': bucket, 'role': role, 'feature_group': group, 'mlflow_arn': arn}, indent=2))
if '--prepare-only' in sys.argv:
    sys.exit(0)
common = [sys.executable, '-u', 'churn_training_skeleton.py', '--feature-group-name', group,
          '--artifacts-bucket', bucket, '--mlflow-arn', arn, '--num-round', '200']
experiments = [('shallow-depth3', 3, .05), ('balanced-depth4', 4, .1), ('complex-depth6', 6, .2)]
rows = []

def run(command, log):
    with open(log, 'w', encoding='utf-8') as f:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
        for line in process.stdout:
            print(line, end='', flush=True); f.write(line); f.flush()
        if process.wait():
            raise RuntimeError(f'Command failed; see {log}')

for name, depth, eta in experiments:
    directory = OUT/'experiments'/name
    directory.mkdir(parents=True, exist_ok=True)
    run(common + ['--run-name', name, '--max-depth', str(depth), '--eta', str(eta),
                  '--output-data-dir', str(directory), '--model-dir', f'model/{name}'], directory/'train.log')
    metrics = json.loads((directory/'evaluation_metrics.json').read_text())
    rows.append({'name': name, 'depth': depth, 'eta': eta, **metrics})
(OUT/'experiment-comparison.json').write_text(json.dumps(rows, indent=2))
best = max(rows, key=lambda r: r['auc_roc'])
print('Selected using INNER VALIDATION AUC only: ' + best['name'], flush=True)
run(common + ['--run-name', 'final-' + best['name'], '--max-depth', str(best['depth']),
              '--eta', str(best['eta']), '--fixed-rounds', str(best['selected_rounds']),
              '--final', '--register', '--model-dir', 'model/final', '--output-data-dir', str(OUT)], OUT/'train-final.log')
