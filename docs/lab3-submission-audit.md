# Lab 3 submission audit — October 17, 2026

Tracks A + B. Reviewed against the supplied full lab guide, including its
October 12 revision. This is a readiness assessment, not a promised grade.

| Rubric item | Points available | Verified evidence |
|---|---:|---|
| Feature Store via Athena | 5 | Live query SUCCEEDED; graded log and SQL export agree |
| Held-out precision and recall | 8 | Recomputed P@10 0.7233 and R@10 0.3288; both pass |
| Recency baseline with lift interval | 7 | AUC 0.7838 vs 0.7229; paired 2,000-resample CI [0.0420, 0.0791] |
| MLflow App experiments | 5 | Four live runs; three distinct development configurations and final run |
| Model Registry | 5 | PendingManualApproval v1; metrics agree; downloaded model matches saved model |
| Tier slices | 5 | Four tiers with counts, positives, AUC, recall, caution flags and weakest-tier discussion |
| End-to-end LLM system | 10 | Fresh live notebook rerun: eight consecutive executed code cells, five offers, no cell errors |
| Track B evaluation | 15 | Four supplied cases, three final judge runs, no NaNs; named judge, per-case means/ranges, claim-specific limitations and measured before/after change |
| Failures and mitigations | 10 | Five real high-risk examples and two observed failures, profiles/chunk IDs/fixes included |
| NorthStar churn design justification | 6 | Dataset size, feature count, interpretability, alternatives and switching criteria |
| Feature-value analysis | 6 | Numerical baseline comparison, gain rankings, weak features and ablation limitation |
| LLM approach and alternative | 5 | RAG vs fine-tuning; changing policy and authoritative eligibility risks |
| More time/data proposal | 3 | Eligibility API, independent claim annotation, temporal validation, calibration and randomized retention experiment |
| Parameterized training | 3 | Hyperparameters and paths accepted as arguments; final log records actual values |
| Existing infrastructure reused | 2 | Bucket, role and Feature Group resolved from existing Terraform outputs |
| No running endpoints/jobs | 2 | Teardown checks rerun after evidence collection; see current teardown output |
| Bedrock prelab checks | 2 | Fresh Titan 1024-dimension and Haiku response checks both PASS |
| README | 1 | Training, evaluation, setup, evidence locations and submission commands documented |

Additional verification: four Task 1 tests and eight Track B tests pass; both
Python environments pass `pip check`. The supplied collector reports
**25 OK, 0 WARN, 0 FAIL**. Saved full and baseline models reproduce all 3,000
holdout predictions; the inference handler agrees. Both plots were visually
inspected. The design is 699 words excluding the track declaration.

This audit added explicit per-customer RAGAS summary statistics and the chunking
rationale. The notebook was rerun live, and usage/cost evidence was refreshed.
Frozen evaluation scores were not replaced or selected for higher results.

## Remaining grading uncertainty

The final RAGAS means are faithfulness 0.2896, answer relevance 0.0781 and context
recall 0.6333. The guide explicitly retires numerical RAGAS targets and awards
evaluation credit for honest repeated results, specific explanations and a
measured change. These are documented. Nonetheless, cautious conditional offers
can sound generic, and two of the five examples use a disclosed safe-copy
fallback after model draft rejection. The grader decides whether the overall
system and written analysis earn full credit. No automatic check can guarantee
100/100.

## Submission boundary

The GitHub remote was checked during this audit: `lab3-submit` was not present
there. Publishing the final local commit/tag and submitting the repository URL
in Canvas remain separate steps. The unrelated untracked `delete_space.py` is
excluded. No submission has been made by this audit.
