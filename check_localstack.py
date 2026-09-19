import json
import boto3

kwargs = dict(
    endpoint_url="http://localhost:4566",
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
)

lines = []


def add(header, value):
    lines.append("== " + header + " ==")
    if isinstance(value, str):
        lines.append(value)
    else:
        lines.append(json.dumps(value, indent=2, default=str))
    lines.append("")


sts = boto3.client("sts", **kwargs)
identity = sts.get_caller_identity()
identity_clean = {}
for k, v in identity.items():
    if k != "ResponseMetadata":
        identity_clean[k] = v
add("sts get-caller-identity", identity_clean)

s3 = boto3.client("s3", **kwargs)
resp = s3.list_objects_v2(Bucket="northstar-local-data-000000000000")
objs = resp.get("Contents", [])
obj_lines = []
for o in objs:
    obj_lines.append(str(o["LastModified"]) + "  " + str(o["Size"]) + "  " + o["Key"])
if obj_lines:
    add("s3 ls (recursive)", "\n".join(obj_lines))
else:
    add("s3 ls (recursive)", "(no objects found)")

iam = boto3.client("iam", **kwargs)
roles = iam.list_roles()["Roles"]
names = []
for r in roles:
    if r["RoleName"].startswith("northstar"):
        names.append(r["RoleName"])
add("iam list-roles (northstar*)", names)

ec2 = boto3.client("ec2", **kwargs)
vpcs = ec2.describe_vpcs()["Vpcs"]
vpc_out = []
for v in vpcs:
    vpc_out.append({"Id": v["VpcId"], "CIDR": v["CidrBlock"]})
add("ec2 describe-vpcs", vpc_out)

subnets = ec2.describe_subnets()["Subnets"]
subnet_out = []
for s in subnets:
    subnet_out.append({"Id": s["SubnetId"], "AZ": s["AvailabilityZone"], "CIDR": s["CidrBlock"]})
add("ec2 describe-subnets", subnet_out)

with open("docs/lab1b-localstack-output.txt", "w") as f:
    f.write("\n".join(lines))

print("Wrote docs/lab1b-localstack-output.txt")
