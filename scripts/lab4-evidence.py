"""Capture actual AWS records before tearing down the Lab 4 stack."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
GROUP = "northstar-churn-models"


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf-8")


def save_log(session, build_id, path):
    build = session.client("codebuild").batch_get_builds(ids=[build_id])["builds"][0]
    logs = build["logs"]
    pages = session.client("logs").get_paginator("filter_log_events").paginate(
        logGroupName=logs["groupName"], logStreamNames=[logs["streamName"]]
    )
    messages = [event["message"].rstrip("\n") for page in pages for event in page["events"]]
    if not messages:
        raise ValueError(f"No log events for {build_id}")
    path.write_text("\n".join(messages) + "\n", encoding="utf-8")
    return build


def packages(sm):
    return [item for page in sm.get_paginator("list_model_packages").paginate(
        ModelPackageGroupName=GROUP, SortBy="CreationTime", SortOrder="Descending"
    ) for item in page["ModelPackageSummaryList"]]


def snapshot(session, label, build_id=None):
    cb, sm, cw = [session.client(name) for name in ("codebuild", "sagemaker", "cloudwatch")]
    if build_id is None:
        build_id = cb.list_builds_for_project(projectName="northstar-ci", sortOrder="DESCENDING")["ids"][0]
    build = cb.batch_get_builds(ids=[build_id])["builds"][0]
    account = session.client("sts").get_caller_identity()["Account"]
    subscriptions = session.client("sns").list_subscriptions_by_topic(
        TopicArn=f"arn:aws:sns:us-east-1:{account}:northstar-model-approvals"
    )["Subscriptions"]
    record = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "build": {key: build.get(key) for key in [
            "id", "resolvedSourceVersion", "buildStatus", "startTime", "endTime", "phases",
        ]},
        "model_packages": packages(sm),
        "alarm": cw.describe_alarms(AlarmNames=["northstar-ci-build-failure"])["MetricAlarms"],
        "alarm_action_history": cw.describe_alarm_history(
            AlarmName="northstar-ci-build-failure", HistoryItemType="Action", MaxRecords=10
        )["AlarmHistoryItems"],
        "subscriptions": [{key: item[key] for key in ["Protocol", "SubscriptionArn"]}
                          for item in subscriptions],
    }
    with (DOCS / "lab4-failure-demo.txt").open("a", encoding="utf-8") as handle:
        handle.write(f"\n===== {label} =====\n")
        handle.write(json.dumps(record, indent=2, default=str) + "\n")
    print(f"Saved {label}: {build['buildStatus']}, {build_id}")


def capture(session, args):
    cb, cp, sm = [session.client(name) for name in ("codebuild", "codepipeline", "sagemaker")]
    build_ids = [item for page in cb.get_paginator("list_builds_for_project").paginate(
        projectName="northstar-ci", sortOrder="DESCENDING") for item in page["ids"]]
    builds = []
    for build_id in build_ids:
        build = cb.batch_get_builds(ids=[build_id])["builds"][0]
        builds.append({key: build.get(key) for key in [
            "id", "resolvedSourceVersion", "buildStatus", "startTime", "endTime", "phases", "logs",
        ]})
    pipeline_runs = [item for page in cp.get_paginator("list_pipeline_executions").paginate(
        pipelineName="northstar-pipeline") for item in page["pipelineExecutionSummaries"]]
    sm_runs = [item for page in sm.get_paginator("list_pipeline_executions").paginate(
        PipelineName="northstar-churn-pipeline") for item in page["PipelineExecutionSummaries"]]
    write_json(DOCS / "lab4-pipeline-runs.txt", {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "CodePipeline": pipeline_runs, "CodeBuild": builds, "SageMakerPipeline": sm_runs,
    })
    green = save_log(session, args.green, DOCS / "lab4-build-green.log")
    failed = save_log(session, args.failed, DOCS / "lab4-build-failed.log")
    assert green["buildStatus"] == "SUCCEEDED"
    assert failed["buildStatus"] == "FAILED"
    write_json(DOCS / "lab4-model-registry.json", {"ModelPackageSummaryList": packages(sm)})
    write_json(DOCS / "lab4-model-package.json",
               sm.describe_model_package(ModelPackageName=args.package_arn))
    print("Saved complete pipeline, build, registry, and lineage evidence")


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    snap = commands.add_parser("snapshot")
    snap.add_argument("--label", required=True)
    snap.add_argument("--build-id")
    log = commands.add_parser("log")
    log.add_argument("--build-id", required=True)
    log.add_argument("--output", required=True)
    cap = commands.add_parser("capture")
    cap.add_argument("--green", required=True)
    cap.add_argument("--failed", required=True)
    cap.add_argument("--package-arn", required=True)
    args = parser.parse_args()
    session = boto3.Session(region_name="us-east-1")
    account = session.client("sts").get_caller_identity()["Account"]
    if account != "701145280839":
        raise RuntimeError(f"Wrong AWS account: {account}")
    DOCS.mkdir(exist_ok=True)
    if args.command == "snapshot":
        snapshot(session, args.label, args.build_id)
    elif args.command == "log":
        save_log(session, args.build_id, Path(args.output))
    else:
        capture(session, args)


if __name__ == "__main__":
    main()
