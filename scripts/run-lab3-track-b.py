"""Run all four supplied cases across three retrieval strategies and two final repetitions."""
import copy
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
os.environ['RAGAS_DO_NOT_TRACK'] = 'true'
import numpy as np
import pandas as pd
import evaluation_harness as eh
from rag.offer_pipeline import OfferRAG, MODEL
from rag.metering import BedrockMeter

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
OUT = ROOT/'docs/lab3-evidence'
OUT.mkdir(exist_ok=True)
pipeline = OfferRAG()
manifest = pipeline.build_index()
(OUT/'rag-chunk-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(f'Indexed {len(manifest["chunks"])} policy chunks using Titan + FAISS', flush=True)
all_frames = []
strategy_offers = {}
for strategy in ['tier', 'constraint', 'hybrid']:
    path = OUT/f'offers-{strategy}.json'
    if path.exists():
        offers = json.loads(path.read_text(encoding='utf-8'))
    else:
        offers = []
        for tc in eh.OFFER_TEST_CASES:
            profile = tc.customer_context | {'customer_id': tc.customer_id}
            result = pipeline.generate_unguarded(profile, tc.question, strategy=strategy, include_profile_context=False)
            result['question'] = tc.question
            offers.append(result)
            print(strategy, tc.customer_id, result['answer'], flush=True)
        path.write_text(json.dumps(offers, indent=2), encoding='utf-8')
    strategy_offers[strategy] = offers

# Generate improved offers once, then judge the same four outputs twice.
final_path = OUT/'offers-final.json'
if final_path.exists():
    final_offers = json.loads(final_path.read_text(encoding='utf-8'))
else:
    final_offers = []
    for tc in eh.OFFER_TEST_CASES:
        result = pipeline.generate(tc.customer_context | {'customer_id': tc.customer_id}, tc.question)
        result['question'] = tc.question
        final_offers.append(result)
        print('FINAL OFFER',tc.customer_id,result['answer'],flush=True)
    final_path.write_text(json.dumps(final_offers,indent=2),encoding='utf-8')

experiments = [('tier', 'baseline-tier', False), ('constraint', 'baseline-constraint', False),
               ('hybrid', 'baseline-hybrid', False), ('hybrid', 'final-1', True), ('hybrid', 'final-2', True), ('hybrid', 'final-3', True)]
for strategy, label, with_profile in experiments:
    result_path = OUT/f'rag_eval_{label}.csv'
    if result_path.exists():
        df = pd.read_csv(result_path)
        if len(df) == 4 and not df[['faithfulness','answer_relevancy','context_recall']].isna().any().any():
            all_frames.append(df)
            print('Reusing completed evaluation:', label, flush=True)
            continue
    offers = copy.deepcopy(final_offers if with_profile else strategy_offers[strategy])
    mapping = {o['customer_profile']['customer_id']: o for o in offers}
    # The supplied harness calls with context only; fixture identity is recovered by tier.
    def invoke(context, question):
        tc = next(c for c in eh.OFFER_TEST_CASES if c.question == question)
        return mapping[tc.customer_id]
    evaluator = eh.RAGEvaluator(invoke, bedrock_model_id=MODEL)
    with BedrockMeter(OUT/'rag-judge-usage.jsonl', label):
        df = evaluator.run(copy.deepcopy(eh.OFFER_TEST_CASES))
        # Retry only failed cases, never replace an unfavourable finite score.
        for attempt in range(3):
            bad = df[['faithfulness','answer_relevancy','context_recall']].isna().any(axis=1)
            if not bad.any():
                break
            for ix in np.flatnonzero(bad.to_numpy()):
                print(f'Retrying failed judge case {ix} for {label}', flush=True)
                retried = evaluator.run([copy.deepcopy(eh.OFFER_TEST_CASES[int(ix)])])
                for metric in ['faithfulness','answer_relevancy','context_recall']:
                    if pd.isna(df.loc[ix, metric]) and pd.notna(retried.iloc[0][metric]):
                        df.loc[ix, metric] = retried.iloc[0][metric]
    (OUT/f'ragas-traces-{label}.json').write_text(json.dumps(evaluator.last_traces,indent=2,default=str),encoding='utf-8')
    df['customer_id'] = [c.customer_id for c in eh.OFFER_TEST_CASES]
    df['run'] = label; df['strategy'] = strategy; df['profile_in_context'] = with_profile
    df['judge_model'] = MODEL
    df.to_csv(result_path, index=False)
    if df[['faithfulness','answer_relevancy','context_recall']].isna().any().any():
        raise RuntimeError(f'Judge failures remain in {label}; do not treat NaN as zero')
    all_frames.append(df)
combined = pd.concat(all_frames, ignore_index=True)
combined.to_csv(OUT/'rag_eval_all.csv', index=False)
final = combined[combined.run.str.startswith('final-')]
final.to_csv(OUT/'rag_eval.csv', index=False)
summary = final.groupby('run')[['faithfulness','answer_relevancy','context_recall']].mean()
summary.to_csv(OUT/'rag_eval_run_means.csv')
print('FINAL RUN MEANS\n'+summary.to_string(), flush=True)
print('OVERALL MEAN/RANGE\n'+summary.agg(['mean','min','max']).to_string(), flush=True)
print('Track B repeated evaluation complete.', flush=True)
