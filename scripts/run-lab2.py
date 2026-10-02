"""Run the deployed lab pipeline and verify an online/offline Feature Store round trip.

Usage: python scripts/run-lab2.py [--project northstar] [--environment dev]
Requires boto3, AWS credentials, and a successfully applied Terraform stack.
"""
import argparse
import json
from pathlib import Path
import time

import boto3

parser = argparse.ArgumentParser()
parser.add_argument("--project", default="northstar")
parser.add_argument("--environment", default="dev")
parser.add_argument("--region", default="us-east-1")
args = parser.parse_args()
session = boto3.Session(region_name=args.region)
s3, glue = session.client("s3"), session.client("glue")
account = session.client("sts").get_caller_identity()["Account"]
prefix = f"{args.project}-{args.environment}"
bucket = f"{prefix}-data-{account}"
root = Path(__file__).resolve().parents[1]


def wait_for(label, inspect, done, timeout=2400):
    deadline = time.monotonic() + timeout
    previous = None
    while time.monotonic() < deadline:
        result = inspect()
        if result != previous:
            print(f"{label}: {result}", flush=True)
            previous = result
        if done(result):
            return result
        time.sleep(20)
    raise TimeoutError(f"{label} exceeded {timeout} seconds")


s3.upload_file(str(root / "northstar-raw-sample.csv"), bucket,
               "raw/customers/northstar-raw-sample.csv")
print(f"Uploaded sample to s3://{bucket}/raw/customers/", flush=True)
crawler = f"{prefix}-raw-crawler"
wait_for("Crawler availability", lambda: glue.get_crawler(Name=crawler)["Crawler"]["State"],
         lambda state: state == "READY")
glue.start_crawler(Name=crawler)
wait_for("Crawler", lambda: glue.get_crawler(Name=crawler)["Crawler"]["State"],
         lambda state: state == "READY")
last_crawl = glue.get_crawler(Name=crawler)["Crawler"].get("LastCrawl", {})
assert last_crawl.get("Status") == "SUCCEEDED", last_crawl
database = f"{args.project}_{args.environment}".replace("-", "_")
table = glue.get_table(DatabaseName=database, Name="customers")["Table"]
print("Catalog schema: " + json.dumps(table["StorageDescriptor"]["Columns"]), flush=True)

for suffix in ("transform", "feature-engineer"):
    job = f"{prefix}-{suffix}"
    run_id = glue.start_job_run(JobName=job)["JobRunId"]
    print(f"{job} run: {run_id}", flush=True)
    state = wait_for(job,
        lambda: glue.get_job_run(JobName=job, RunId=run_id)["JobRun"]["JobRunState"],
        lambda value: value in {"SUCCEEDED", "FAILED", "TIMEOUT", "STOPPED", "ERROR", "EXPIRED"})
    if state != "SUCCEEDED":
        run = glue.get_job_run(JobName=job, RunId=run_id)["JobRun"]
        raise RuntimeError(f"{job}: {run.get('ErrorMessage', state)}")

group = f"{prefix}-customer-features"
runtime = session.client("sagemaker-featurestore-runtime")
record = runtime.get_record(FeatureGroupName=group,
    RecordIdentifierValueAsString="CUST-10000776").get("Record", [])
assert len(record) == 16, f"Expected 16 features, got {len(record)}"
print("PASS: online GetRecord returned all 16 features", flush=True)


def offline_count():
    return sum(1 for page in s3.get_paginator("list_objects_v2").paginate(
        Bucket=bucket, Prefix="features/offline-store/")
        for obj in page.get("Contents", []) if obj["Key"].endswith(".parquet"))


count = wait_for("Offline Parquet file count", offline_count, lambda n: n > 0, timeout=1800)
print(f"PASS: Feature Store offline storage contains {count} Parquet files", flush=True)
