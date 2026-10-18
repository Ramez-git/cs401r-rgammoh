"""Check the saved Track B artifacts; no model calls or AWS credentials needed."""
import json
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from rag.offer_pipeline import OfferRAG, chunks_from_corpus, ROOT
E=ROOT/'docs/lab3-evidence'
results=pd.read_csv(E/'rag_eval.csv')
metrics=['faithfulness','answer_relevancy','context_recall']
assert results.run.nunique() >= 2
assert results.groupby('run').customer_id.nunique().eq(4).all()
assert results.groupby(['run','customer_id']).size().eq(1).all()
assert np.isfinite(results[metrics].to_numpy()).all()
assert ((results[metrics]>=0)&(results[metrics]<=1)).all().all()
assert results.judge_model.str.contains('claude-haiku-4-5').all()
print(f'PASS: all four cases in {results.run.nunique()} complete final evaluations; no NaN scores')
nb=json.loads((ROOT/'notebooks/lab3-demo.ipynb').read_text(encoding='utf-8'))
cells=[c for c in nb['cells'] if c['cell_type']=='code' and ''.join(c['source']).strip()]
assert [c['execution_count'] for c in cells] == list(range(1,len(cells)+1))
assert all(c.get('outputs') for c in cells)
assert not any(o.get('output_type')=='error' for c in cells for o in c['outputs'])
print(f'PASS: clean demo notebook with {len(cells)} consecutive executed code cells and saved outputs')
manifest=json.loads((E/'rag-chunk-manifest.json').read_text())
assert manifest['chunks']==chunks_from_corpus(ROOT/'northstar-policy-docs')
ids={c['id'] for c in manifest['chunks']}
examples=json.loads((E/'high-risk-offers.json').read_text())
assert len(examples)==5
holdout=pd.read_csv(E/'holdout-predictions.csv').set_index('customer_id')
for offer in examples+json.loads((E/'offers-final.json').read_text()):
    p=offer['customer_profile']
    assert f'If your account confirms {p["loyalty_tier"]} status' in offer['answer']
    assert len(re.findall(r'[.!?](?:\s|$)',offer['answer']))==3
    assert any(c.lower() in offer['answer'].lower() for c in p['top_categories'])
    assert set(offer['chunk_ids']) <= ids
    assert offer['profile_context'] in offer['contexts']
for offer in examples:
    p=offer['customer_profile'];row=holdout.loc[p['customer_id']]
    assert bool(row.selected_top10)
    assert abs(row.probability-p['churn_probability'])<1e-6
print('PASS: five real top-decile examples, conditional eligibility and traceable policy chunks')
safety=json.loads((E/'rag-safety-tests.json').read_text())
assert len(safety)>=3 and all(r['passed'] and r['boundary_refusal'] for r in safety)
print('PASS: saved injection, final-sale and expired-offer boundary cases')
design=(ROOT/'docs/lab3-model-design.md').read_text(encoding='utf-8-sig')
assert design.startswith('Track selection: A + B')
words=len(design.split('\n',1)[1].split())
assert 600<=words<=850
assert (E/'track-b-examples.md').read_text().count('## Observed failure:') >=2
assert (ROOT/'docs/lab3-track-b-report.md').exists()
print(f'PASS: design declaration, approximately 700-word justification ({words}), and two documented failures')
print('TRACK B ARTIFACT VERIFICATION PASSED')
