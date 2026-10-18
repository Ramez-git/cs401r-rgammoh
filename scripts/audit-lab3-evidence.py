"""Exhaustive file-format and numerical checks supporting the manual Lab 3 audit."""
import ast
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
from PIL import Image
from sklearn.metrics import roc_auc_score
import xgboost as xgb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rag.offer_pipeline import OfferRAG, chunks_from_corpus
E = ROOT/'docs/lab3-evidence'
inventory = []
paths = subprocess.check_output(['git','diff','--name-only','c7b3913^'], cwd=ROOT, text=True).splitlines()
paths += ['scripts/audit-lab3-evidence.py', 'docs/lab3-manual-review.md']
for name in sorted(set(paths)):
    path = ROOT/name
    if not path.is_file() or name.endswith('deep-audit.json'):
        continue
    raw = path.read_bytes()
    entry = {'path':name, 'bytes':len(raw), 'sha256':hashlib.sha256(raw).hexdigest()}
    if path.suffix == '.png':
        with Image.open(io.BytesIO(raw)) as picture:
            entry['dimensions'] = list(picture.size)
            picture.verify()
        entry['check'] = 'PNG integrity'
    else:
        text = raw.decode('utf-8-sig')
        entry['lines'] = len(text.splitlines())
        entry['check'] = 'UTF-8 text decoded in full'
        if path.suffix == '.py':
            ast.parse(text)
            entry['check'] = 'Python syntax parsed'
        elif path.suffix in {'.json','.ipynb'}:
            json.loads(text)
            entry['check'] = 'JSON parsed in full'
        elif path.suffix == '.jsonl':
            entry['records'] = len([json.loads(line) for line in text.splitlines() if line.strip()])
            entry['check'] = 'Every JSONL record parsed'
        elif path.suffix == '.csv':
            rows = list(csv.reader(io.StringIO(text)))
            assert rows and all(len(row) == len(rows[0]) for row in rows), name
            entry['records'] = len(rows)-1
            entry['check'] = 'Every CSV record parsed; column widths consistent'
    inventory.append(entry)

checks = []
final_split = pd.read_csv(E/'split-membership.csv').set_index('customer_id').partition
for directory in [E, *sorted((E/'experiments').iterdir())]:
    frame = pd.read_csv(directory/'holdout-predictions.csv')
    metadata = json.loads((directory/'run-metadata.json').read_text())
    metrics = json.loads((directory/'evaluation_metrics.json').read_text())
    features = metadata['feature_columns']
    scores = []
    for filename, columns, saved in [('model.json', features, 'probability'), ('baseline.json',['days_since_last_purchase'],'baseline_probability')]:
        model = xgb.Booster()
        model.load_model(directory/filename)
        predicted = model.predict(xgb.DMatrix(frame[columns]))
        np.testing.assert_allclose(predicted, frame[saved], atol=1e-7, rtol=0)
        scores.append(predicted)
    selected = np.zeros(len(frame), dtype=bool)
    selected[np.argsort(-scores[0],kind='stable')[:int(np.ceil(len(frame)*.1))]] = True
    np.testing.assert_array_equal(selected, frame.selected_top10)
    y = frame.churn_label.to_numpy()
    for key,value in {'auc_roc':roc_auc_score(y,scores[0]),'baseline_auc':roc_auc_score(y,scores[1]),'precision_top10':y[selected].mean(),'recall_top10':y[selected].sum()/y.sum()}.items():
        assert abs(round(value,4)-metrics[key]) < 1e-9, (directory,key)
    split = pd.read_csv(directory/'split-membership.csv').set_index('customer_id').partition
    pd.testing.assert_series_equal(split.sort_index(), final_split.sort_index())
    expected_partition = 'test' if directory == E else 'training'
    assert final_split.loc[frame.customer_id].eq(expected_partition).all()
    for row in pd.read_csv(directory/'slice-evaluation.csv').itertuples():
        mask = frame.loyalty_tier.eq(row.tier).to_numpy()
        n, positive = int(mask.sum()), int(y[mask].sum())
        assert (n,positive) == (row.n,row.positives)
        assert abs(roc_auc_score(y[mask], scores[0][mask])-row.auc) < 1e-10
        assert abs(y[mask & selected].sum()/positive-row.recall) < 1e-10
        assert row.too_small == (n < 100 or min(positive,n-positive) < 20)
    checks.append(f'{directory.relative_to(ROOT)}: every prediction, top-decile membership, metrics, slice and outer split checked')

chunks = {c['id']:c for c in chunks_from_corpus(ROOT/'northstar-policy-docs')}
offer_files = [*E.glob('offers-*.json'), E/'high-risk-offers.json', E/'notebook-live-offers.json']
offer_count = 0
for path in offer_files:
    for offer in json.loads(path.read_text()):
        offer_count += 1
        assert [chunks[c]['text'] for c in offer['chunk_ids']] == offer['contexts'][:len(offer['chunk_ids'])], path
        for attempt in offer.get('draft_attempts',[]):
            assert OfferRAG.validate_copy(attempt['draft'], offer['customer_profile']) == attempt['errors'], path
checks.append(f'All {offer_count} saved offers: retrieved text matches canonical chunks; draft verdicts unchanged by defensive fix')

metrics = ['faithfulness','answer_relevancy','context_recall']
combined = pd.read_csv(E/'rag_eval_all.csv')
for label,group in combined.groupby('run'):
    single = pd.read_csv(E/f'rag_eval_{label}.csv')
    pd.testing.assert_frame_equal(group.reset_index(drop=True), single, check_dtype=False)
    offers = json.loads((E/('offers-final.json' if label.startswith('final') else f'offers-{label.removeprefix("baseline-")}.json')).read_text())
    answer_column = 'response' if 'response' in single else 'answer'
    assert single[answer_column].tolist() == [o['answer'] for o in offers]
    assert np.isfinite(single[metrics].to_numpy()).all()
final = combined[combined.run.str.startswith('final-')].reset_index(drop=True)
pd.testing.assert_frame_equal(final,pd.read_csv(E/'rag_eval.csv'),check_dtype=False)
checks.append('All 24 baseline/final evaluation rows reconcile; responses match frozen generation evidence')
for name in ['rag-usage.jsonl','rag-judge-usage.jsonl']:
    rows = [json.loads(line) for line in (E/name).read_text().splitlines() if line.strip()]
    assert len({r['request_id'] for r in rows}) == len(rows), name
    assert all(r['input_tokens'] >= 0 and r['output_tokens'] >= 0 and r['latency_ms'] >= 0 for r in rows)
    checks.append(f'{name}: {len(rows)} unique requests; all token counts and latencies nonnegative')

output = {'scope':'Every file introduced or modified since the pre-Lab-3 commit; numeric records checked programmatically, not claimed as hand arithmetic.', 'inventory':inventory,'checks':checks}
(E/'deep-audit.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
print(f'Parsed {len(inventory)} Lab 3 files completely.')
print('\n'.join(checks))
print('DEEP EVIDENCE AUDIT PASSED')
