# Track B: retention-offer implementation and evaluation

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

| run | faithfulness | answer_relevancy | context_recall |
|---|---:|---:|---:|
| constraint | 0.1131 | 0.2726 | 0.2250 |
| hybrid | 0.2222 | 0.3654 | 0.4458 |
| tier | 0.2430 | 0.3337 | 0.4042 |

Hybrid had the highest measured context recall (0.4458);
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
| faithfulness | 0.2222 | 0.2896 | +0.0674 |
| answer_relevancy | 0.3654 | 0.0781 | -0.2874 |
| context_recall | 0.4458 | 0.6333 | +0.1875 |

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

| run | faithfulness | answer_relevancy | context_recall |
|---|---:|---:|---:|
| final-1 | 0.3312 | 0.0834 | 0.6333 |
| final-2 | 0.2687 | 0.0754 | 0.6333 |
| final-3 | 0.2687 | 0.0754 | 0.6333 |

| run | mean | minimum_run_mean | maximum_run_mean |
|---|---:|---:|---:|
| faithfulness | 0.2896 | 0.2687 | 0.3312 |
| answer_relevancy | 0.0781 | 0.0754 | 0.0834 |
| context_recall | 0.6333 | 0.6333 | 0.6333 |

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
  producing a mean of 0.6333. The Platinum trace attributes
  the benefit list but cannot attribute the reference's margin-destruction
  advice or the claim that an unused credit is the strongest lever. Those are
  grading commentary, not policy facts. Bronze's reference similarly includes
  proportional-incentive and cross-category strategy beyond the policy corpus.
  Adding the profile supports customer facts but cannot add missing policy.

## Failures and production limitations

`track-b-examples.md` contains five actual high-risk profiles/offers and two
specific observed failures, each with retrieved chunk IDs and a fix. The final
pipeline's safety checks cover injection, final-sale overrides and expired-offer
reinstatement. Those checks are narrow request-boundary and rendering tests;
they do not demonstrate universal jailbreak resistance. Regex validation can
miss paraphrases. The renderer supports a restricted points/credit offer space;
unknown policy formats cause omission rather than a guessed entitlement.

The primary production dependency is an authoritative eligibility service for
current tier, unused credits, destination and product eligibility. The current
system explicitly conditions benefits instead of inventing these facts.
Conditional copy remains generic and sometimes falls back after rejected model
drafts. Before deployment, use verified account facts, a policy-aware grammar,
and human-reviewed customer-facing offers, then measure real retention outcomes.

## Cost and reproducibility

Metered successful requests across development, evaluation, audit and the clean
notebook total an estimated **$0.5654** in model usage.
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
