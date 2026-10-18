# Detailed Lab 3 review — October 17, 2026

This review supplements the rubric checklist in `lab3-submission-audit.md`.
Scope is the Lab 3 submission, including retained development evidence, rather
than all third-party package internals or unrelated earlier labs.

## Inspection method and coverage

Manual code review covered the training entry point, experiment runner,
inference handler, retrieval/chunking/embedding pipeline, both generation paths,
validator and renderer, metering wrapper, harness, example builder, notebook
builder, collectors, teardown, verification/tests and report generators.
The supplied harness was diffed against the starter: the four Track B fixtures
and metric definitions remain unchanged. Unused Track C starter code is retained
and is not an implemented or submitted Track C system.

Manual content review covered all four policy documents, the original/corrected
prompt templates and actual system prompts, all 26 saved offers (12 baseline,
four final harness, five examples, five notebook outputs), the four diagnostic
judge cases, every notebook cell's saved text/table output, both final plots
and all six experiment plots. The evaluation and design reports were compared
with actual metrics, policies and traces. Setup, restore, training, generation,
evaluation and teardown logs were reviewed for provenance and failure outcomes;
Terraform recovery/cleanup resource lists were checked against those outcomes.

Large generated arrays, CSV rows, usage records and serialized trees were
parsed and checked programmatically. They were not each recalculated by hand.
`scripts/audit-lab3-evidence.py` records the complete file inventory, SHA-256,
format checks and numerical cross-checks in `lab3-evidence/deep-audit.json`.
This distinction matters: a full-file parse is not a claim that every byte was
visually inspected. AWS provenance was checked through service APIs and exports,
not by clicking through every console screen. Third-party dependency source and
every possible adversarial input are outside the review.

## Findings fixed

1. The standalone `evaluation_harness.py --track B` command still invoked the
   starter placeholder. The working experiment runner already used the actual
   pipeline. The CLI now uses that same pipeline and honors region/model flags;
   a focused test verifies the wiring and output-file creation.
2. A malformed model tool response could crash `validate_copy` while inspecting
   a non-string recommendation or non-object draft. Such responses now reject
   cleanly and enter the existing retry/fallback path. Regression tests cover
   null, list, string and numeric malformed inputs. Every saved draft produces
   exactly its original validation outcome after this defensive change.
3. The three development confusion matrices incorrectly said "Test predictions"
   even though their data is inner validation. Titles now say "Inner-validation";
   plots were regenerated from the unchanged saved models/predictions. Final
   test results, splits and selected configuration did not change.
4. Teardown stopped transform jobs but did not include them in its verification
   list, and its default region variable was not exported. Both are corrected.
5. The Windows-only `pywin32` dependency is now platform-conditional. This removes
   an obvious non-Windows installation blocker; a clean Linux install was not
   performed, and compatibility of every dependency on every platform is not
   claimed.
6. The report now names a real retrieval miss: Bronze's retrieved evidence omits
   the $7.95 return fee. The low recall is not attributed entirely to the harness.
   It also acknowledges unsupported implications in final copy, described below.
7. Starter-template annotations and runner comments now distinguish historical
   guidance from actual prompts and three final judge repetitions.

## Evidence reconciliation

- All four saved full models and four recency baselines reproduce their saved
  predictions: 3,000 final rows and 1,400 rows for each development configuration.
- Exact top-decile membership, AUC, precision, recall and every tier's counts,
  AUC, recall and small-sample flag reconcile. All four outer split manifests
  agree; development evaluation customers are in the outer training partition.
- All 26 saved offers' retrieved passages match the canonical corpus chunks.
  All 24 combined evaluation rows match their individual run files and frozen
  offer text. Twelve final rows cover all four cases in three runs.
- Usage logs contain 103 unique pipeline request IDs and 320 unique judge
  request IDs, with nonnegative tokens and latency. These remain observed
  successful-call costs, not an account invoice.
- The final model's Athena query, MLflow run, registry metadata and registered
  S3 artifact were checked live in the preceding verification. The supplied
  collector again reports 25 OK, zero warnings and zero failures.
- Four training tests and ten Track B tests pass after these changes.

## Limitations that remain visible

The final Silver harness offer says "see what's waiting for you" and "items
that match your style". These imply account availability or personal preference
beyond verified facts. Similar wording occurs in other saved offers. The report
now acknowledges this as a real weakness, not solely a judge error. A fixed
neutral account-check sentence and stricter recommendation grammar are proposed
mitigations requiring a new generation/evaluation experiment. This audit does
not silently replace scored offers or claim that proposal has been measured.

Additional historical errors were identified while reading the baseline offers:
the hybrid Platinum offer converts two points per dollar into "$5 ... every
$250", which is wrong given 100 points = $5; some baseline shipping/return copy
also omits eligibility limits. These are retained failed development outputs,
not advertised as correct examples. Final monetary language comes from the
retrieved policy renderer, which does not make that conversion.

The corrected tier-template copy is teaching/reference material. The preserved
starter also includes obsolete numerical targets and unsafe advice; neither is
the final system prompt. Profile-only historical scores and the two-run log are
superseded by the explicit three-run final CSV/report, not deleted.

The validator uses a restricted regex, not a complete policy verifier. The
Platinum renderer recognizes the current corpus wording and is not a general
parser for arbitrary future policy revisions. Boundary refusals cover the saved
cases, not every jailbreak. Two of five examples use disclosed fallback copy.
The model scores are not calibrated probabilities, and the holdout is a customer
split on synthetic data, not prospective evidence of retention uplift.

The submission contains the required deliverables and passes objective checks.
These remaining qualitative limitations prevent a promise of a perfect grade.
GitHub publication and Canvas submission are still outstanding.
