"""Export Task 1 AWS evidence using the supplied collector, without claiming Tasks 2-4 are done."""
import json
import os
from pathlib import Path
import sys
import boto3
import collect_lab3_evidence as collect
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
out = 'docs/lab3-evidence'
sess = boto3.Session(region_name='us-east-1')
collect.dump(f'{out}/account.json', sess.client('sts').get_caller_identity())
metrics = collect.check_metrics()
collect.export_athena(sess, out, Path(out, 'train-final.log').read_text(encoding='utf-8'))
collect.export_mlflow(sess, out, 'northstar-mlflow', 'northstar-churn', metrics)
collect.export_registry(sess, out, 'northstar-churn-models', metrics)
collect.check_slices()
if any(level == 'FAIL' for level, _, _ in collect.results):
    sys.exit(1)
print('PASS: Task 1 AWS exports and metric consistency')
