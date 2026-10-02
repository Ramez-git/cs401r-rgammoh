"""Verify every customer in the latest feature snapshot reached the offline store.

Run after scripts/run-lab2.py. Requires boto3, pandas and pyarrow.
Offline delivery can take several minutes; this check waits up to 30 minutes.
"""
import argparse
from io import BytesIO
import time

import boto3
import pandas as pd

parser = argparse.ArgumentParser()
parser.add_argument("--project", default="northstar")
parser.add_argument("--environment", default="dev")
parser.add_argument("--region", default="us-east-1")
args = parser.parse_args()
session = boto3.Session(region_name=args.region)
s3 = session.client("s3")
account = session.client("sts").get_caller_identity()["Account"]
bucket = f"{args.project}-{args.environment}-data-{account}"


def keys(prefix):
    return [obj["Key"] for page in s3.get_paginator("list_objects_v2").paginate(
        Bucket=bucket, Prefix=prefix) for obj in page.get("Contents", [])
        if obj["Key"].endswith(".parquet")]


def read(key):
    return pd.read_parquet(BytesIO(s3.get_object(Bucket=bucket, Key=key)["Body"].read()))


expected = pd.concat([read(key) for key in keys("features/customers/")], ignore_index=True)
assert expected.event_time.nunique() == 1, "Features contain mixed snapshots"
snapshot = float(expected.event_time.iloc[0])
customer_ids = set(expected.customer_id)
cache = {}
previous = None
deadline = time.monotonic() + 1800
while time.monotonic() < deadline:
    for key in keys("features/offline-store/"):
        if key not in cache:
            cache[key] = read(key)
    received = pd.concat(list(cache.values()), ignore_index=True) if cache else pd.DataFrame()
    if not received.empty:
        received = received[pd.to_numeric(received.event_time) == snapshot]
    actual_ids = set(received.customer_id) if not received.empty else set()
    status = (len(actual_ids & customer_ids), len(cache))
    if status != previous:
        print(f"Offline snapshot {snapshot}: {status[0]}/{len(customer_ids)} customers, {status[1]} Parquet files", flush=True)
        previous = status
    if actual_ids == customer_ids:
        actual = received.drop_duplicates("customer_id").set_index("customer_id").sort_index()
        want = expected.set_index("customer_id").sort_index()
        for col in want.columns:
            if col == "loyalty_tier":
                assert actual[col].equals(want[col]), f"Offline mismatch: {col}"
            else:
                assert ((pd.to_numeric(actual[col]) - pd.to_numeric(want[col])).abs() < 0.00001).all(), f"Offline mismatch: {col}"
        print(f"PASS: all {len(customer_ids)} customers and all feature values match the offline store", flush=True)
        break
    time.sleep(30)
else:
    raise TimeoutError("Offline store did not receive the complete feature snapshot")
