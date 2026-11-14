"""Run the Lab 5 synthetic canary and capture each evidence window."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time

import boto3


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "deployment" / "configs"
EVIDENCE = ROOT / "docs" / "lab5-deployment-output.txt"
REGION = "us-east-1"
ENDPOINT = "northstar-churn-prod"
GROUP = "northstar-churn-models"
MODELS = {"northstar-churn-v2": 2, "northstar-churn-v3": 3}
TARGET = "endpoint/northstar-churn-prod/variant/champion"
ALARM_PREFIX = "northstar-churn-rollback"
MONITOR_SECONDS = 60 * 60


def config(name):
    return json.loads((CONFIG / name).read_text(encoding="utf-8"))


def cli(*args):
    return subprocess.check_output(
        ["aws", "--region", REGION, "--no-cli-pager", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    ).strip()


def log(message):
    print(message, flush=True)
    with EVIDENCE.open("a", encoding="utf-8", newline="\n") as output:
        print(message, file=output)


def section(heading):
    log(f"\n===== {heading}  ({datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}) =====")


def inventory(session):
    sm = session.client("sagemaker")
    autoscaling = session.client("application-autoscaling")
    queries = [
        ("endpoints", sm, "list_endpoints", "Endpoints", {}),
        ("endpoint configs", sm, "list_endpoint_configs", "EndpointConfigs", {}),
        ("models", sm, "list_models", "Models", {}),
        ("scalable targets", autoscaling, "describe_scalable_targets", "ScalableTargets",
         {"ServiceNamespace": "sagemaker"}),
        ("transform jobs running", sm, "list_transform_jobs", "TransformJobSummaries",
         {"StatusEquals": "InProgress"}),
        ("processing jobs running", sm, "list_processing_jobs", "ProcessingJobSummaries",
         {"StatusEquals": "InProgress"}),
    ]
    return {
        label: sum(len(page[key]) for page in client.get_paginator(operation).paginate(**params))
        for label, client, operation, key, params in queries
    }


def traffic(runtime, payload, requests):
    counts = Counter()
    for _ in range(requests):
        result = runtime.invoke_endpoint(EndpointName=ENDPOINT, ContentType="text/csv", Body=payload)
        with result["Body"] as body:
            body.read()
        counts[result["InvokedProductionVariant"]] += 1
    return counts


def monitor(runtime, cloudwatch, payload, alarm_name, counts, started):
    next_probe = started + 60
    while (remaining := started + MONITOR_SECONDS - time.monotonic()) > 0:
        time.sleep(max(0, min(remaining, next_probe - time.monotonic())))
        counts.update(traffic(runtime, payload, 30))
        alarm = cloudwatch.describe_alarms(AlarmNames=[alarm_name])["MetricAlarms"][0]
        if alarm["StateValue"] == "ALARM":
            return counts, alarm["StateValue"], alarm["StateReason"]
        next_probe += 60
    return counts, alarm["StateValue"], alarm["StateReason"]


def capture_data(session, destination):
    bucket, prefix = destination.removeprefix("s3://").split("/", 1)
    s3 = session.client("s3")
    for variant in ("champion", "canary"):
        result = s3.list_objects_v2(Bucket=bucket, Prefix=f"{prefix}{ENDPOINT}/{variant}/")
        objects = [item["Key"] for item in result.get("Contents", []) if item["Key"].endswith(".jsonl")]
        if not objects:
            raise RuntimeError(f"SageMaker has written no {variant} capture files")
        log(f"Data capture verified for {variant}: s3://{bucket}/{objects[0]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bash", default="bash", help="Bash executable used for rollback and teardown")
    args = parser.parse_args()
    os.environ["AWS_DEFAULT_REGION"] = REGION
    session = boto3.Session(region_name=REGION)
    sm = session.client("sagemaker")
    runtime = session.client("sagemaker-runtime")
    cloudwatch = session.client("cloudwatch")
    account = session.client("sts").get_caller_identity()["Account"]
    endpoint_config = config("endpoint-config-canary.json")
    alarm = config("rollback-alarm.json")
    destination = endpoint_config["DataCaptureConfig"]["DestinationS3Uri"]
    if destination != f"s3://northstar-dev-data-{account}/datacapture/":
        raise SystemExit("The capture bucket and active AWS account differ")
    existing = inventory(session)
    if any(existing.values()) or cloudwatch.describe_alarms(AlarmNamePrefix=ALARM_PREFIX)["MetricAlarms"]:
        raise SystemExit(f"Teardown is account-wide. Resolve existing SageMaker resources first: {existing}")

    packages = {
        name: f"arn:aws:sagemaker:{REGION}:{account}:model-package/{GROUP}/{version}"
        for name, version in MODELS.items()
    }
    for package in packages.values():
        if sm.describe_model_package(ModelPackageName=package)["ModelApprovalStatus"] != "Approved":
            raise SystemExit(f"Model owner approval is required: {package}")
    payload = (CONFIG / "sample.csv").read_bytes()
    role = f"arn:aws:iam::{account}:role/northstar-dev-MLEngineer"
    EVIDENCE.write_text("", encoding="utf-8")
    log(f"Lab 5 deployment evidence - account {account}, region {REGION}")
    section("0. Model Registry: versions and approval status")
    log(cli("sagemaker", "list-model-packages", "--model-package-group-name", GROUP,
            "--query", "ModelPackageSummaryList[].[ModelPackageVersion,ModelApprovalStatus,CreationTime]",
            "--output", "table"))
    log(cli("sagemaker", "describe-model-package", "--model-package-name", packages["northstar-churn-v3"],
            "--query", "ApprovalDescription", "--output", "text"))

    created_endpoint = False
    try:
        for name, package in packages.items():
            sm.create_model(ModelName=name, PrimaryContainer={"ModelPackageName": package},
                            ExecutionRoleArn=role)
        sm.create_endpoint_config(**endpoint_config)
        sm.create_endpoint(EndpointName=ENDPOINT, EndpointConfigName=endpoint_config["EndpointConfigName"])
        created_endpoint = True
        print(f"Waiting for {ENDPOINT} to become InService", flush=True)
        sm.get_waiter("endpoint_in_service").wait(EndpointName=ENDPOINT)

        section("1. describe-endpoint: both variants and their weights")
        log(cli("sagemaker", "describe-endpoint", "--endpoint-name", ENDPOINT, "--query",
                "{Status:EndpointStatus,Config:EndpointConfigName,Variants:ProductionVariants[]."
                "{Name:VariantName,Weight:CurrentWeight,Instances:CurrentInstanceCount}}"))
        log(cli("sagemaker", "describe-endpoint-config", "--endpoint-config-name",
                endpoint_config["EndpointConfigName"], "--query",
                "{Variants:ProductionVariants[].[VariantName,ModelName,InstanceType,InitialVariantWeight],"
                "Capture:DataCaptureConfig}"))

        section("2. auto-scaling: scalable target, policy and endpoint quota")
        log(cli("application-autoscaling", "register-scalable-target", "--cli-input-json",
                "file://deployment/configs/scalable-target.json"))
        log(cli("application-autoscaling", "put-scaling-policy", "--cli-input-json",
                "file://deployment/configs/scaling-policy.json"))
        for operation in ("describe-scalable-targets", "describe-scaling-policies"):
            log(cli("application-autoscaling", operation, "--service-namespace", "sagemaker",
                    "--resource-ids" if operation == "describe-scalable-targets" else "--resource-id", TARGET))
        log(cli("service-quotas", "get-service-quota", "--service-code", "sagemaker", "--quota-code",
                "L-614B09FD", "--query", "Quota.[QuotaName,Value]", "--output", "table"))

        section("3. rollback alarm: definition as code, then live state")
        cloudwatch.put_metric_alarm(**alarm)
        log(json.dumps(alarm, indent=2))
        log(cli("cloudwatch", "describe-alarms", "--alarm-name-prefix", ALARM_PREFIX, "--query",
                "MetricAlarms[].[AlarmName,MetricName,ExtendedStatistic,Threshold,EvaluationPeriods,StateValue]",
                "--output", "table"))

        section("4. observed traffic split at 9:1")
        started = time.monotonic()
        initial = traffic(runtime, payload, 200)
        log(f"Observed over 200 untargeted calls: {dict(sorted(initial.items()))}")
        if set(initial) != {"champion", "canary"}:
            raise RuntimeError("Both variants must serve requests during the 9:1 test")
        total, status, reason = monitor(runtime, cloudwatch, payload, alarm["AlarmName"], initial.copy(), started)
        elapsed = time.monotonic() - started
        log(f"Observed over {elapsed / 60:.1f} minutes: {dict(sorted(total.items()))}")
        log(f"Canary alarm at end of observation: {status} ({reason})")
        capture_data(session, destination)

        subprocess.run([args.bash, "deployment/configs/rollback-action.sh"], cwd=ROOT, check=True)
        sm.get_waiter("endpoint_in_service").wait(EndpointName=ENDPOINT)
        section("5. after rollback: weights, then observed split")
        log(cli("sagemaker", "describe-endpoint", "--endpoint-name", ENDPOINT, "--query",
                "ProductionVariants[].[VariantName,CurrentWeight]", "--output", "text"))
        after = traffic(runtime, payload, 100)
        log(f"Observed over 100 untargeted calls: champion {after['champion']} / canary {after['canary']}")
        if after != {"champion": 100}:
            raise RuntimeError("Rollback failed to route all traffic to the champion")
    finally:
        if created_endpoint:
            print(f"Deleting {ENDPOINT} and waiting for release", flush=True)
            sm.delete_endpoint(EndpointName=ENDPOINT)
            sm.get_waiter("endpoint_deleted").wait(EndpointName=ENDPOINT)
        subprocess.run([args.bash, "scripts/teardown-lab5.sh"], cwd=ROOT, check=True)
        section("6. after teardown: live API")
        remaining = inventory(session)
        for label, count in remaining.items():
            log(f"{label}: {count}")
        if any(remaining.values()) or cloudwatch.describe_alarms(AlarmNamePrefix=ALARM_PREFIX)["MetricAlarms"]:
            raise RuntimeError("Live API reports remaining inference resources")


if __name__ == "__main__":
    main()
