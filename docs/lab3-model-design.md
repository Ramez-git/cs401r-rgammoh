Track selection: A + B — churn prediction and policy-grounded retention offers

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
0.2896, relevance 0.0781, and context recall 0.6333.
Faithfulness improves over the original hybrid baseline, while relevance falls.
Judge traces show conditions converted into unconditional statements and cautious
offers marked noncommittal. Reference marketing commentary also has no policy
source. I preserve those low scores and the tradeoff instead of claiming success
against retired targets. With ten times the resources, I would integrate an
authoritative eligibility API, use independently annotated claim-level evaluation,
and prospectively test customer outcomes. Temporal backtesting, calibration and
a randomized retention experiment would distinguish predicting churn from actually
preventing it.
