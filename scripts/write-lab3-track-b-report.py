"""Write Track B evidence and ~700-word design from actual completed runs."""
import json
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'docs/lab3-evidence'
metrics=['faithfulness','answer_relevancy','context_recall']
results=pd.read_csv(E/'rag_eval.csv')
all_results=pd.read_csv(E/'rag_eval_all.csv')
run_means=results.groupby('run')[metrics].mean()
means=run_means.mean()
base=all_results[all_results.run=='baseline-hybrid'][metrics].mean()
retrieval=all_results[all_results.run.str.startswith('baseline')].groupby('strategy')[metrics].mean()
def table(frame):
    return '| '+ ' | '.join(['run']+list(frame.columns))+' |\n|---|'+'---:|'*len(frame.columns)+'\n'+'\n'.join('| '+str(ix)+' | '+' | '.join(f'{v:.4f}' for v in row)+' |' for ix,row in frame.iterrows())
summary=pd.DataFrame({'mean':means,'minimum_run_mean':run_means.min(),'maximum_run_mean':run_means.max()})
case_summary=results.groupby('customer_id')[metrics].agg(['mean','min','max'])
case_summary.columns=['_'.join(column) for column in case_summary.columns]
case_summary.to_csv(E/'rag-per-case-summary.csv')
# Costs include all logged development, judge audit and notebook calls, not only final runs.
usage=[]
for filename,component in [('rag-usage.jsonl','pipeline'),('rag-judge-usage.jsonl','judge')]:
    for line in (E/filename).read_text().splitlines():
        if line.strip():
            usage.append(json.loads(line)|{'component':component})
u=pd.DataFrame(usage)
u['estimated_usd']=u.apply(lambda r: (r.input_tokens*.02/1e6) if 'titan' in r.model else (r.input_tokens*1.1+r.output_tokens*5.5)/1e6,axis=1)
cost=u.groupby(['component','model']).agg(requests=('request_id','count'),input_tokens=('input_tokens','sum'),output_tokens=('output_tokens','sum'),estimated_usd=('estimated_usd','sum'))
cost.to_csv(E/'rag-cost-summary.csv')
(E/'rag-cost-assumptions.json').write_text(json.dumps({'haiku_us_profile_estimate_per_million_input_usd':1.1,'haiku_us_profile_estimate_per_million_output_usd':5.5,'titan_v2_per_million_input_usd':.02,'sources':['https://platform.claude.com/docs/en/about-claude/pricing','https://aws.amazon.com/bedrock/pricing/','https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/current/us-east-1/index.json'],'method':'Haiku global list rates plus published 10% regional/multi-region premium. Estimate, not invoice; excludes failed/unobserved SDK retries, access checks and other AWS services.'},indent=2),encoding='utf-8')

report=f'''# Track B: retention-offer implementation and evaluation

## Implemented system

Task 1 scores determine the top-decile high-risk customers. The five examples
come from the actual test-set predictions, one from each loyalty tier plus one
additional high-risk customer. Product categories are joined from Lab 2 processed
transactions on or before 2026-04-01, ranked by purchase count, with alphabetical
tie-breaking. These are observed categories, not a catalog or invented products.
No outcome-window purchases are used for personalization.

The corpus is the four supplied Markdown policies. Splitting preserves Markdown
sections, caps the body at 220 whitespace-delimited words, and uses 40-word
overlap within long sections. Table sections stay together when they fit; each
chunk retains its source document, heading and stable ID. The resulting 54 chunks
and their full texts are saved in `rag-chunk-manifest.json`. Titan Text Embeddings
V2 (`amazon.titan-embed-text-v2:0`) produces normalized 1024-dimensional vectors.
FAISS IndexFlatIP performs exact cosine retrieval locally. Embeddings are cached
by text/model hash, so changed documents are embedded again.

The 220-word cap keeps individual policy provisions focused for retrieval while
preserving short tables and their eligibility conditions. The 40-word overlap
reduces loss of context at long-section boundaries. These are practical choices
for this small corpus, not parameters established as optimal by an ablation.

Titan keeps embedding and judge authentication inside the existing AWS account;
there is no demonstrated need for Cohere-specific multilingual capability in
this small English corpus. Local FAISS avoids the idle cost and setup of an
OpenSearch collection. Haiku 4.5 through the `us.` inference profile is sufficient
for short structured drafts; the US routing profile follows the course's data
location choice. A stronger generator cannot supply missing eligibility facts.
Only temperature is set, never temperature and topP together.

Three retrieval implementations were measured with the original free-form
prompt and policy-only judge contexts: A, tier entitlements (top 6); B, constraints
(top 6); C, hybrid (top 4 entitlements filtered to loyalty/shipping plus top 4
constraints filtered to source policies, deduplicated). There is no learned
reranker. Metadata filtering and union preserve governing policy evidence rather
than adding another model call over a 54-chunk corpus.

{table(retrieval)}

Hybrid had the highest measured context recall ({retrieval.loc['hybrid','context_recall']:.4f});
this is one comparison over four fixtures, not a statistically established ranking.

## Prompt audit and factual corrections

The original templates are preserved in `offer_generation_prompts.starter.md`.
The corrected working copy fixes all three planted facts:

1. Gold is $2,000–$4,999.99 trailing 12-month spend, not $2,000–$9,999.99.
2. Platinum starts at $5,000, not $10,000.
3. Gold does not receive free expedited shipping on orders over $200. No tier
   receives free expedited shipping (POL-SHP-007 section 2).

The two documented design weaknesses are also addressed. Every request supplies
the tier and observed category history, and numeric channel/diversity signals
are interpreted as mostly-online/in-store and narrow/broad category history.
The final structured system prompt is `prompt_templates/final_offer_system.md`;
`freeform_offer_system.md` preserves the earlier prompt used in the baseline.

## Measured pipeline change

Free-form generation produced factual errors despite instructions. The final
pipeline asks Haiku for two neutral sentences via a required tool schema. It
validates the draft, retries once after a rejection, and records a deterministic
fallback when the model still fails. The middle sentence is rendered from a
retrieved loyalty points row or a conditional Platinum gear-credit provision.
It never treats lifetime spend as proof of a current tier or an unused reward.
This narrows generation authority while retaining model-written category copy.
The customer profile is also supplied as a judge context. These are a **bundled
change**, so the experiment does not isolate each component's effect.

| Metric | Free-form hybrid before | Final mean after | Difference |
|---|---:|---:|---:|
'''+ '\n'.join(f'| {m} | {base[m]:.4f} | {means[m]:.4f} | {means[m]-base[m]:+.4f} |' for m in metrics)+f'''

Judgement: the change prevents the documented unconditional tier/expiry claims
and improves measured faithfulness and context recall relative to the original
hybrid baseline. Answer relevance worsens substantially. The result is safer
copy with weaker marketing directness, not an across-the-board quality win.
The profile-only intermediate experiment is preserved under
`profile-only-audit/`; its higher faithfulness did not fix unsafe unconditional
claims. No finite unfavourable score was replaced or discarded.

## Repeated final evaluation

The supplied RAGAS harness ran all four cases **three times**, judging the same
four frozen offers to expose judge variability. RAGAS 0.4.3 uses Haiku 4.5
`us.anthropic.claude-haiku-4-5-20251001-v1:0` as judge and Titan V2 for relevance
embeddings. The scores below are actual outputs. No NaN remains; the runner
retries only failed judge cases, never finite low scores. The full guide's
October 12 update removes the old numeric score targets from grading.

{table(run_means)}

{table(summary)}

Per-customer mean and range across the three final judge runs (also exported in
`rag-per-case-summary.csv`):

{table(case_summary)}

Per-case scores are in `rag_eval.csv`; judge traces from the diagnostic third
run are in `ragas-traces-final-3.json`. They explain each metric's limits:

- **Faithfulness:** in Gold case CUST-10000317, the statement generator turns
  “If your account confirms Gold status” into the unconditional statement that
  the account confirms it. That unsupported statement is then penalized. It also
  treats category invitations and account-check instructions as factual claims
  requiring policy support. The trace accepts the 1.5-point policy rate while
  rejecting several of these derived claims. The low score therefore includes
  judge decomposition errors; it does not excuse actual baseline hallucinations.
- **Answer relevance:** Gold, Bronze and Platinum receive zero in these runs.
  The judge explicitly marks the conditional offers `noncommittal=1`; RAGAS
  multiplies relevance by zero in that case. This is a real directness tradeoff:
  uncertain eligibility demands conditions, but the harness interprets that
  caution as evasiveness. Its reverse-generated questions also differ from
  the instruction “Generate a retention offer.” Silver remains nonzero.
- **Context recall:** Gold and Silver score 1.0, Bronze 0.2 and Platinum 0.3333,
  producing a mean of {means['context_recall']:.4f}. The Platinum trace attributes
  the benefit list but cannot attribute the reference's margin-destruction
  advice or the claim that an unused credit is the strongest lever. Those are
  grading commentary, not policy facts. Bronze's reference similarly includes
  proportional-incentive and cross-category strategy beyond the policy corpus.
  Bronze also misses a real retrievable fact: the $7.95 return-shipping fee in
  POL-RET-004 section 6.2 was not retrieved. Its low recall therefore reflects
  both retrieval coverage and reference design, not just a harness defect.
  Adding the profile supports customer facts but cannot add missing policy.

## Failures and production limitations

`track-b-examples.md` contains five actual high-risk profiles/offers and two
specific observed failures, each with retrieved chunk IDs and a fix. The final
pipeline's safety checks cover injection, final-sale overrides and expired-offer
reinstatement. Those checks are narrow request-boundary and rendering tests;
they do not demonstrate universal jailbreak resistance. Regex validation can
miss paraphrases. The renderer supports a restricted points/credit offer space;
unknown policy formats cause omission rather than a guessed entitlement.

Manual review also found residual unsupported wording in the final Silver
harness offer: "see what's waiting for you" can imply an existing account offer,
and "items that match your style" assumes preference beyond category history.
The judge is reasonable to flag those claims. A proposed next revision would
use a fixed neutral account-check sentence and restrict recommendations to
observed categories without style or availability claims, followed by a new
repeated evaluation. The frozen scores here describe the current copy; they are
not evidence that this proposed revision has been implemented or measured.

The primary production dependency is an authoritative eligibility service for
current tier, unused credits, destination and product eligibility. The current
system explicitly conditions benefits instead of inventing these facts.
Conditional copy remains generic and sometimes falls back after rejected model
drafts. Before deployment, use verified account facts, a policy-aware grammar,
and human-reviewed customer-facing offers, then measure real retention outcomes.

## Cost and reproducibility

Metered successful requests across development, evaluation, audit and the clean
notebook total an estimated **${u.estimated_usd.sum():.4f}** in model usage.
`rag-cost-summary.csv` separates pipeline and judge tokens; raw logs contain
model IDs, request IDs, token counts and latency. The estimate uses published
Haiku list rates with the regional/multi-region premium and Titan's US East
on-demand rate; it is not a billing invoice and excludes other AWS services.
Sources: [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing),
[AWS Bedrock pricing](https://aws.amazon.com/bedrock/pricing/), and the
[AWS public regional price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/current/us-east-1/index.json).
No hosted vector store, persistent endpoint or AgentCore stack was created.

The saved notebook ran in a fresh Python 3.12 kernel with consecutive execution
counts and live Bedrock outputs. See `docs/lab3-checks.md` for replay and live
verification commands. Changes to the supplied harness retain its scoring
metrics/cases: explicit Bedrock judge wiring, a two-worker limit, trace export,
and labeling old targets as ungraded. The final result records both low scores
and why they occurred.
The standalone Track B harness CLI is also wired to the same pipeline. A later
defensive validator fix rejects malformed tool-response types; all saved valid
drafts retain their original validation outcomes.
'''
(ROOT/'docs/lab3-track-b-report.md').write_text(report,encoding='utf-8')

examples=['# Track B examples and observed failures','', 'These five profiles were selected by the Task 1 model, not invented for the demo.','Category histories use only pre-cutoff transactions. Every offer is conditional on verified eligibility.','']
for i,r in enumerate(json.loads((E/'high-risk-offers.json').read_text()),1):
    examples += [f'## Successful example {i}: {r["customer_profile"]["customer_id"]}', '',
                 'Profile:', '```json',json.dumps(r['customer_profile'],indent=2),'```','',
                 'Generated offer:','',r['answer'],'', 'Retrieved chunk IDs: '+', '.join(r['chunk_ids']),
                 '',f'Safe copy fallback used: {r.get("safe_fallback",False)}. The policy incentive is rendered from retrieved evidence.','']
failures=[('constraint','CUST-10000904','Points expiration hallucination',
    'The offer says points never expire. POL-LOY-011 section 3.1 says they expire 18 months after the most recent qualifying purchase. Constraint retrieval did not return that section; the free-form model filled the gap incorrectly.',
    'Restrict benefit claims to parsed retrieved policy, and omit expiration promises when its rule is absent. Implemented in the final renderer; never inventing an expiry term is preferable to guessing.'),
    ('hybrid','CUST-10000588','Lifetime spend incorrectly treated as an imminent tier upgrade',
    'The offer claims the member is just $15 from Gold, using $1,985 lifetime value. Policy uses trailing 12-month qualifying spend. The policy threshold was retrieved, but the model applied it to the wrong definition.',
    'Resolve tier from the system of record in production. Until that integration exists, keep Silver benefits conditional and never compute a tier-upgrade gap from lifetime value. The final renderer follows that constraint.')]
for strategy,cid,title,why,fix in failures:
    r=next(r for r in json.loads((E/f'offers-{strategy}.json').read_text()) if r['customer_profile']['customer_id']==cid)
    examples += [f'## Observed failure: {title}','', 'Profile:','```json',json.dumps(r['customer_profile'],indent=2),'```','', 'Original generated offer:','',r['answer'],'','Retrieved chunk IDs: '+', '.join(r['chunk_ids']),'','Why it fails: '+why,'','Fix: '+fix,'']
(E/'track-b-examples.md').write_text('\n'.join(examples),encoding='utf-8')

# Approximately 700 words, separate from the Task 1 evaluation report.
design=f'''Track selection: A + B — churn prediction and policy-grounded retention offers

# Model design justification

NorthStar has approximately 10,000 labeled customers and 13 candidate tabular
features, with roughly 22% churn. Gradient boosting is a practical choice because
recency, purchase frequency, basket value and channel mix can interact
nonlinearly. Logistic regression would need manually chosen transformations and
interactions to express those relationships. A neural network introduces more
tuning and calibration work without a large training population or an obvious
representation-learning advantage. XGBoost also exposes feature importance and
supports customer-level explanations that the retention team can inspect. Gain
importance is descriptive, however, and should not be presented as causality.
I would reconsider the model for substantially larger behavioral sequences,
rich product text, or evidence that a simpler calibrated model preserves the
same ranking at lower operating cost.

The final model uses 11 numeric features. Customer identifiers and the label
never enter the feature matrix; loyalty tier is reserved for slices, and the
hand-written churn-risk heuristic is excluded. Numeric missing values retain
XGBoost's native missing-value treatment. A stratified 30% test split is held
apart while three configurations compete on an inner validation partition.
The chosen depth-three, learning-rate-0.05 model is refitted for 154 rounds on
6,999 training customers. Class weighting is derived from that partition:
5,459 negatives divided by 1,540 positives, approximately 3.545. Model scores
are useful rankings; probability calibration has not been established.

Feature engineering bought measurable value. Full-model test AUC is 0.7838
against 0.7229 for a trained recency-only model. The difference is +0.0609,
with a paired 2,000-resample 95% bootstrap interval [0.0420, 0.0791]. Precision
among the 300 contacted customers is 0.7233 and recall is 0.3288. Recency still
has the largest average split gain, about 82.1, followed by 180-day frequency
at 50.7 and 30-day frequency at 31.9. Category diversity, channel ratio and
tenure have much smaller gains, approximately 14.6, 13.5 and 11.5. Their low
rankings should not be concealed, but neither proves dispensability when
predictors overlap. A training-only ablation would test that claim. Silver has
the weakest slice AUC, while Gold has the lowest global-budget recall; Platinum's
strong AUC rests on only 21 churners and warrants caution.

Track B uses retrieval rather than fine-tuning because the knowledge is a small,
versioned policy corpus whose rates and eligibility rules can change. Fine-tuning
would not establish current entitlement or give reliable source attribution.
Titan V2 embeddings, normalized to 1024 dimensions, support a free local FAISS
index. Section-aware chunks use 220 words with 40-word overlap in long sections.
Two retrieval passes combine tier entitlements with policy restrictions; no
learned reranker is justified for 54 chunks. In the initial comparison, hybrid
context recall was 0.4458 versus 0.4042 for tier-only and 0.2250 for constraints.
These four-case estimates guide development, not a production performance claim.

The main production risk is promising a benefit the customer cannot use. The
Feature Store derives tier from lifetime value while policy uses trailing
12-month spend. Therefore the offer cannot confidently infer current status,
remaining credits, or distance to an upgrade. Three planted template errors
were corrected: Gold ends at $4,999.99, Platinum begins at $5,000, and free
expedited shipping exists at no tier. Free-form generation nevertheless invented
non-expiring points and a $15 upgrade gap. The final pipeline uses Haiku for
structured category copy, validates it, and renders conditional incentives from
retrieved policy. This intentionally limits creative authority; repeated draft
failures fall back to a recorded safe invitation.

All four training runs retain parameters and metrics in the existing MLflow
App. The registered model stays PendingManualApproval. Infrastructure names
come from Terraform outputs, and successful model requests are metered separately
for generation and judging. Local training and FAISS avoid persistent inference
capacity while preserving reproducible saved evidence.

Evaluation remains imperfect. Three final harness runs average faithfulness
{means['faithfulness']:.4f}, relevance {means['answer_relevancy']:.4f}, and context recall {means['context_recall']:.4f}.
Faithfulness improves over the original hybrid baseline, while relevance falls.
Judge traces show conditions converted into unconditional statements and cautious
offers marked noncommittal. Reference marketing commentary also has no policy
source. I preserve those low scores and the tradeoff instead of claiming success
against retired targets. With ten times the resources, I would integrate an
authoritative eligibility API, use independently annotated claim-level evaluation,
and prospectively test customer outcomes. Temporal backtesting, calibration and
a randomized retention experiment would distinguish predicting churn from actually
preventing it.
'''
(ROOT/'docs/lab3-model-design.md').write_text(design,encoding='utf-8')
print('Design word count excluding declaration:',len(design.split('\n',1)[1].split()))
print('Estimated logged model usage USD:',round(float(u.estimated_usd.sum()),4))
print('Wrote design, evaluation report, examples and cost evidence.')
