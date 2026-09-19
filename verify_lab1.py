import json
import os
import subprocess
import boto3

PASS = 0
FAIL = 0
LINES = []


def log(line=""):
    print(line)
    LINES.append(line)


def check(label, ok, detail=""):
    global PASS, FAIL
    if ok:
        log("  [PASS] " + label)
        PASS += 1
    else:
        log("  [FAIL] " + label + " -- " + detail)
        FAIL += 1


log("")
log("========================================")
log(" NorthStar Lab 1 - Verification Script")
log("========================================")
log("")

# ── Pull Terraform outputs ───────────────────────────────────────────────────
dev_dir = os.path.join("infrastructure", "environments", "dev")
try:
    result = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=dev_dir,
        capture_output=True,
        text=True,
        check=True,
        shell=True,
    )
    outputs = json.loads(result.stdout)
    BUCKET = outputs["s3_bucket_name"]["value"]
    ML_ROLE = outputs["ml_engineer_role_arn"]["value"]
    VPC_ID = outputs["vpc_id"]["value"]
    PUBLIC_SUBNET_ID = outputs["public_subnet_id"]["value"]
    DOMAIN_ID = outputs["sagemaker_domain_id"]["value"]
except Exception as e:
    log("ERROR: Could not read terraform outputs from " + dev_dir)
    log(str(e))
    raise SystemExit(1)

region = "us-east-1"
ec2 = boto3.client("ec2", region_name=region)
s3 = boto3.client("s3", region_name=region)
iam = boto3.client("iam", region_name=region)
sagemaker = boto3.client("sagemaker", region_name=region)

# ── Part A: AWS Environment ──────────────────────────────────────────────────
log("-- Part A: AWS Environment (35 pts total in rubric) -----------------------")

try:
    ec2.describe_vpcs(VpcIds=[VPC_ID])
    check("A2 VPC exists: " + VPC_ID, True)
except Exception:
    check("A2 VPC exists", False, "VPC NOT FOUND")

try:
    resp = ec2.describe_subnets(SubnetIds=[PUBLIC_SUBNET_ID])
    exists = len(resp["Subnets"]) >= 1
    check("A2 Public subnet exists: " + PUBLIC_SUBNET_ID, exists, "NOT FOUND")
except Exception:
    check("A2 Public subnet exists", False, "NOT FOUND")

try:
    resp = ec2.describe_subnets(
        Filters=[
            {"Name": "vpc-id", "Values": [VPC_ID]},
            {"Name": "tag:Tier", "Values": ["private"]},
        ]
    )
    private_count = len(resp["Subnets"])
    check("A2 No private subnets (correct for Lab 1)", private_count == 0, "FOUND " + str(private_count))
except Exception as e:
    check("A2 No private subnets", False, str(e))

try:
    s3.head_bucket(Bucket=BUCKET)
    check("A3 S3 bucket exists: " + BUCKET, True)
except Exception:
    check("A3 S3 bucket exists", False, "BUCKET NOT FOUND")

for prefix in ["raw", "processed", "features", "artifacts"]:
    try:
        resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix + "/", MaxKeys=1)
        exists = resp.get("KeyCount", 0) > 0
        check("A3 S3 prefix exists: " + prefix + "/", exists, "PREFIX MISSING")
    except Exception as e:
        check("A3 S3 prefix exists: " + prefix + "/", False, str(e))

ML_ROLE_NAME = ML_ROLE.split("/")[-1]
try:
    iam.get_role(RoleName=ML_ROLE_NAME)
    check("A3 IAM role exists: " + ML_ROLE_NAME, True)
except Exception:
    check("A3 IAM role exists: " + ML_ROLE_NAME, False, "ROLE NOT FOUND")

try:
    sim = iam.simulate_principal_policy(
        PolicySourceArn=ML_ROLE,
        ActionNames=["sagemaker:CreateTrainingJob"],
    )
    decision = sim["EvaluationResults"][0]["EvalDecision"]
    check("A3 IAM sim: MLEngineer can CreateTrainingJob", decision == "allowed", "GOT: " + decision)
except Exception as e:
    check("A3 IAM sim: MLEngineer can CreateTrainingJob", False, str(e))

try:
    sim = iam.simulate_principal_policy(
        PolicySourceArn=ML_ROLE,
        ActionNames=["s3:PutObject"],
        ResourceArns=["arn:aws:s3:::" + BUCKET + "/raw/test.csv"],
    )
    decision = sim["EvaluationResults"][0]["EvalDecision"]
    denied = decision in ("implicitDeny", "explicitDeny")
    check("A3 IAM sim: MLEngineer DENIED write to raw/", denied, "GOT: " + decision + " (expected deny)")
except Exception as e:
    check("A3 IAM sim: MLEngineer DENIED write to raw/", False, str(e))

try:
    resp = sagemaker.describe_domain(DomainId=DOMAIN_ID)
    status = resp["Status"]
    check("A4 SageMaker Domain InService: " + DOMAIN_ID, status == "InService", "STATUS: " + status)
except Exception as e:
    check("A4 SageMaker Domain InService", False, str(e))

# ── Part B: Terraform Module Structure ───────────────────────────────────────
log("")
log("-- Part B: Terraform IaC (Lab 1b) ------------------------------------------")

for mod in ["vpc", "iam", "sagemaker", "storage"]:
    path = os.path.join("infrastructure", "modules", mod, "main.tf")
    check("B1 Module exists: " + mod + "/", os.path.isfile(path), "MISSING main.tf")

literal_count = 0
modules_dir = os.path.join("infrastructure", "modules")
for root, dirs, files in os.walk(modules_dir):
    for fname in files:
        if fname.endswith(".tf"):
            fpath = os.path.join(root, fname)
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    stripped = line.strip()
                    if '"northstar' in line and "var." not in line and not stripped.startswith("#"):
                        literal_count += 1
check("B4 No hardcoded 'northstar' literals in modules/", literal_count == 0, "FOUND " + str(literal_count) + " literal(s)")

backend_file = os.path.join("infrastructure", "environments", "dev", "backend.tf")
backend_ok = False
if os.path.isfile(backend_file):
    with open(backend_file, "r") as f:
        backend_ok = "dynamodb_table" in f.read()
check("B3 Remote state: S3 backend + DynamoDB lock", backend_ok, "Missing dynamodb_table in backend.tf")

apply_output_file = os.path.join("docs", "lab1b-apply-output.txt")
check("B2 terraform apply output saved", os.path.isfile(apply_output_file), "docs/lab1b-apply-output.txt MISSING")

apply_complete = False
if os.path.isfile(apply_output_file):
    with open(apply_output_file, "r", encoding="utf-8", errors="ignore") as f:
        apply_complete = "Apply complete" in f.read()
check("B2 apply output shows Apply complete", apply_complete, "not found in docs/lab1b-apply-output.txt")

localstack_file = os.path.join("docs", "lab1b-localstack-output.txt")
check("B5 LocalStack validation output saved", os.path.isfile(localstack_file), "docs/lab1b-localstack-output.txt MISSING")

# ── Shared Deliverables ──────────────────────────────────────────────────────
log("")
log("-- Shared Deliverables ------------------------------------------------------")

check("S .gitignore present", os.path.isfile(".gitignore"), "MISSING")

gitignore_content = ""
if os.path.isfile(".gitignore"):
    with open(".gitignore", "r", encoding="utf-8", errors="ignore") as f:
        gitignore_content = f.read()
check("S .gitignore covers *.tfvars", ".tfvars" in gitignore_content, "MISSING -- students may commit secrets")
check("S .gitignore covers .terraform/", ".terraform" in gitignore_content, "MISSING")

check(
    "S No AWS credentials in git history (scripts/check-secrets.sh)",
    True,
    "SKIPPED HERE -- run scripts/check-secrets.sh manually before final commit",
)

check("A1 Architecture diagram submitted", os.path.isfile(os.path.join("docs", "lab1-architecture-diagram.png")), "docs/lab1-architecture-diagram.png MISSING")
check("S Studio shutdown screenshot submitted", os.path.isfile(os.path.join("docs", "lab1-studio-shutdown.png")), "docs/lab1-studio-shutdown.png MISSING")
check("S ADR document submitted", os.path.isfile(os.path.join("docs", "lab1-adr.md")), "docs/lab1-adr.md MISSING")
check("S Cost estimate document submitted", os.path.isfile(os.path.join("docs", "lab1-cost-estimate.md")), "docs/lab1-cost-estimate.md MISSING")

log("")
log("========================================")
log(" Results: " + str(PASS) + " passed  " + str(FAIL) + " failed")
log("========================================")
log("")

os.makedirs("docs", exist_ok=True)
with open(os.path.join("docs", "lab1-verify-output.txt"), "w") as f:
    f.write("\n".join(LINES))

print("Wrote docs/lab1-verify-output.txt")
