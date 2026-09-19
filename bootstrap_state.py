import boto3
import botocore

region = "us-east-1"

sts = boto3.client("sts", region_name=region)
account_id = sts.get_caller_identity()["Account"]

state_bucket = "northstar-tfstate-" + account_id
lock_table = "northstar-tfstate-lock"

print("Account ID :", account_id)
print("Region     :", region)
print("State bucket:", state_bucket)
print("Lock table :", lock_table)
print("")

s3 = boto3.client("s3", region_name=region)

try:
    s3.head_bucket(Bucket=state_bucket)
    print("[SKIP] S3 bucket already exists:", state_bucket)
except botocore.exceptions.ClientError:
    print("[CREATE] S3 bucket:", state_bucket)
    s3.create_bucket(Bucket=state_bucket)

print("[SET] Versioning on state bucket")
s3.put_bucket_versioning(
    Bucket=state_bucket,
    VersioningConfiguration={"Status": "Enabled"},
)

print("[SET] Block public access on state bucket")
s3.put_public_access_block(
    Bucket=state_bucket,
    PublicAccessBlockConfiguration={
        "BlockPublicAcls": True,
        "IgnorePublicAcls": True,
        "BlockPublicPolicy": True,
        "RestrictPublicBuckets": True,
    },
)

print("[SET] Server-side encryption on state bucket")
s3.put_bucket_encryption(
    Bucket=state_bucket,
    ServerSideEncryptionConfiguration={
        "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
    },
)

dynamodb = boto3.client("dynamodb", region_name=region)

try:
    dynamodb.describe_table(TableName=lock_table)
    print("[SKIP] DynamoDB table already exists:", lock_table)
except botocore.exceptions.ClientError:
    print("[CREATE] DynamoDB lock table:", lock_table)
    dynamodb.create_table(
        TableName=lock_table,
        AttributeDefinitions=[{"AttributeName": "LockID", "AttributeType": "S"}],
        KeySchema=[{"AttributeName": "LockID", "KeyType": "HASH"}],
        BillingMode="PAY_PER_REQUEST",
    )
    print("[WAIT] Waiting for table to become active...")
    waiter = dynamodb.get_waiter("table_exists")
    waiter.wait(TableName=lock_table)

backend_file = "infrastructure/environments/dev/backend.tf"
backend_example = backend_file + ".example"

import os

if not os.path.exists(backend_file) and os.path.exists(backend_example):
    print("[COPY]", backend_example, "->", backend_file)
    with open(backend_example, "r") as f:
        content = f.read()
    with open(backend_file, "w") as f:
        f.write(content)

with open(backend_file, "r") as f:
    content = f.read()

if "YOUR_ACCOUNT_ID" in content:
    print("[PATCH] Updating", backend_file, "with account ID")
    content = content.replace("YOUR_ACCOUNT_ID", account_id)
    with open(backend_file, "w") as f:
        f.write(content)
    print("        Done. Review the change before committing.")
else:
    print("[SKIP] backend.tf already patched")

print("")
print("==> Bootstrap complete.")
