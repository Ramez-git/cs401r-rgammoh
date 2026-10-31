"""Audit the submission evidence against the lab's concrete requirements."""
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def read(name):
    path = DOCS / name
    assert path.is_file() and path.stat().st_size > 0, f"Missing or empty {path.name}"
    return path.read_text(encoding="utf-8-sig")


def main():
    green = read("lab4-build-green.log")
    failed = read("lab4-build-failed.log")
    for filename, minimum in [("test_data.py", 2), ("test_features.py", 5),
                              ("test_model.py", 2), ("test_fairness.py", 2)]:
        passed = len(re.findall(rf"tests/{re.escape(filename)}::[^\n]*\bPASSED\b", green))
        assert passed >= minimum, f"{filename}: only {passed} passing tests"
    assert not re.search(r"tests/\S+[^\n]*\b(?:SKIPPED|FAILED|ERROR)\b", green)
    assert "Pipeline succeeded" in green and "Registered: arn:aws:sagemaker:" in green
    assert "FAIRNESS REVIEW:" in green
    champion = re.search(r"champion v(\d+) auc=([.\d]+); candidate auc=([.\d]+)", green)
    assert champion, "Missing actual champion comparison warning"
    assert "Phase complete: PRE_BUILD State: FAILED" in failed
    assert "deliberate" in failed.lower()

    demo = read("lab4-failure-demo.txt")
    blocks = re.split(r"\n===== (.*?) =====\n", demo)
    snapshots = {blocks[i]: json.loads(blocks[i + 1]) for i in range(1, len(blocks), 2)}
    before, red, after = [snapshots[label] for label in ["BEFORE", "AFTER FAILED RUN", "AFTER REVERT"]]
    before_packages = {p["ModelPackageArn"] for p in before["model_packages"]}
    red_packages = {p["ModelPackageArn"] for p in red["model_packages"]}
    after_packages = {p["ModelPackageArn"] for p in after["model_packages"]}
    assert before_packages == red_packages, "Failed pre-build registered a package"
    assert len(after_packages - before_packages) == 1, "Revert must register exactly one new package"
    assert red["build"]["buildStatus"] == "FAILED"
    assert after["build"]["buildStatus"] == "SUCCEEDED"
    phases = {p["phaseType"]: p.get("phaseStatus") for p in red["build"]["phases"]}
    assert phases["PRE_BUILD"] == "FAILED" and "BUILD" not in phases
    for snap, expected in [(before, "OK"), (red, "ALARM"), (after, "OK")]:
        assert snap["alarm"][0]["StateValue"] == expected
    assert any("Successfully executed action" in event["HistorySummary"] for event in red["alarm_action_history"])
    assert any(s["Protocol"] == "email" and s["SubscriptionArn"].startswith("arn:")
               for s in red["subscriptions"]), "Email subscription was not confirmed"
    for snap in [red, after]:
        sha = snap["build"]["resolvedSourceVersion"]
        subprocess.run(["git", "merge-base", "--is-ancestor", sha, "main"], cwd=ROOT, check=True)

    registry = json.loads(read("lab4-model-registry.json"))["ModelPackageSummaryList"]
    statuses = {int(p["ModelPackageVersion"]): p["ModelApprovalStatus"] for p in registry}
    assert statuses[int(champion.group(1))] == "Approved"
    package = json.loads(read("lab4-model-package.json"))
    assert package["ModelApprovalStatus"] == "PendingManualApproval"
    assert package["ModelPackageArn"] in after_packages - before_packages
    metadata = package["CustomerMetadataProperties"]
    assert metadata["training_data_s3_uri"].startswith("s3://")
    assert float(metadata["training_data_event_time"]) > 0
    assert metadata["code_commit_sha"] == after["build"]["resolvedSourceVersion"]
    for field in ["auc_roc", "baseline_auc", "precision_top10", "recall_top10",
                  "lift_ci_low", "lift_ci_high", "fairness_recall_gap"]:
        assert metadata[field]

    runs = json.loads(read("lab4-pipeline-runs.txt"))
    for snap in [red, after]:
        sha = snap["build"]["resolvedSourceVersion"]
        assert any(
            run.get("trigger", {}).get("triggerType") in {"Webhook", "WebhookV2"}
            and any(revision.get("revisionId") == sha for revision in run.get("sourceRevisions", []))
            for run in runs["CodePipeline"]
        ), f"No automatic GitHub push execution recorded for {sha}"
    build = next(b for b in runs["CodeBuild"] if b["id"] == after["build"]["id"])
    assert build["buildStatus"] == "SUCCEEDED" and build["pytest_summaries"]
    assert any(p["phaseType"] == "POST_BUILD" and p["phaseStatus"] == "SUCCEEDED" for p in build["phases"])
    tracking = read("lab4-mlflow-runs.txt")
    assert ":mlflow-app/" in tracking and "params.max_depth" in tracking and "metrics.auc_roc" in tracking
    assert len(set(re.findall(r"\b[0-9a-f]{32}\b", tracking))) >= 3
    assessment = read("lab4-xops-assessment.md")
    for heading in ["Pipeline Stage Mapping", "Champion-Challenger", "Retraining Triggers",
                    "DataOps Maturity", "MLOps Maturity"]:
        assert f"## {heading}" in assessment
    image = DOCS / "lab4-alarm-email.png"
    assert image.is_file() and image.stat().st_size > 1000, "Missing delivered alarm email screenshot"
    assert image.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    print("PASS: test coverage, green/failed runs, champion, failure isolation, alarm delivery, "
          "lineage, MLflow, assessment and Git history")


if __name__ == "__main__":
    main()
