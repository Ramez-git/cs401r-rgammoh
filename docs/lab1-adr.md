## ADR-001: NorthStar Platform Foundation

### Status
Accepted

### Context

NorthStar Retail is building a shared AI platform to support three systems: a churn
prediction model, an offer-generation engine, and a customer service agent backed
by an LLM. All three will eventually be built, trained, and served by different
specialists — a data engineer preparing raw feeds, an ML engineer training and
registering models, and (in later labs) a model monitor watching production
behavior. Because these systems share the same underlying customer data and the
same AWS account, the platform needs an identity model and a storage tier
structure from day one, not bolted on later. Without role separation, any engineer
working on churn scoring could accidentally read or overwrite the raw ingestion
data feeding the customer service agent, and there would be no way to trace which
system touched which data. Without a storage tier structure, there is no
enforceable boundary between "data as ingested" and "data safe to train against,"
which matters when the offer-generation model and the churn model are trained by
different people on different schedules. Lab 1 builds the minimum foundation
every later lab depends on: one VPC, one S3 bucket with staged prefixes, one IAM
role, and one SageMaker Domain for interactive development.

### Decision

The platform runs in a single VPC (`northstar-dev-vpc`, `10.0.0.0/16`) with one
public subnet (`northstar-dev-public-1`, `10.0.100.0/24`) in `us-east-1a`. An
Internet Gateway and a public route table (`0.0.0.0/0` → IGW) give the subnet
outbound internet access, which SageMaker Studio needs to pull training container
images from ECR, reach the S3 API, and serve its own UI. A security group scopes
inbound traffic to the VPC's own CIDR block only — nothing on the internet can
reach the SageMaker Domain directly, even though the subnet itself is "public" in
routing terms. This is a deliberate simplification for Lab 1: NorthStar has one
role and one workload today, so a private-subnet-plus-NAT-gateway topology would
add cost and complexity with no current benefit. That tradeoff is explicitly
temporary — Lab 2 moves Studio into a private subnet once a second role
(DataEngineer) exists and the extra isolation starts paying for itself.

Storage is one S3 bucket (`northstar-dev-data-{account-id}`) organized into four
prefixes — `raw/`, `processed/`, `features/`, and `artifacts/` — that mirror the
data lifecycle from ingestion to trained model output. Versioning and SSE-S3
encryption are enabled, and all public access is blocked. The prefix structure
exists now, even though only `artifacts/` and `features/` are used in Lab 1,
because NorthStar's DataEngineer role (added in Lab 2) needs `raw/` and
`processed/` to already be there rather than requiring a bucket layout migration
mid-project.

Identity is enforced through one IAM role, `northstar-dev-MLEngineer`, trusted by
`sagemaker.amazonaws.com`. Its inline policy is scoped by data stage, not just by
service: it can read and write `artifacts/` and `features/` — the stages an ML
engineer legitimately owns — but has no S3 permissions on `raw/` or `processed/`
at all. This is enforced at the ARN level (`.../artifacts/*` and `.../features/*`,
not a bucket-wide wildcard), so the omission is structural rather than a policy
authors just forgot to add. The role also carries a narrow "Studio self-service"
statement (describe/list/create/delete on its own domain, user profile, space,
and app resources) because Studio literally runs as this role — without it,
opening Studio fails with a permissions error before any real work happens.

SageMaker Studio (`northstar-dev-domain`) is the shared development environment
for all three AI systems in this course: IAM auth mode, VPC-only network access,
and `northstar-dev-MLEngineer` as its default execution role.

### Consequences

#### What this makes easy
Any future ML engineer working on churn prediction, offer generation, or the
service-agent model gets consistent, least-privilege access on day one — no
per-project IAM work. Adding a second engineer means adding a user profile under
the existing domain, not building new infrastructure. The four-prefix bucket
layout means Lab 2's DataEngineer role can be added by writing one new IAM policy
statement, not restructuring storage.

#### What this makes harder
A public subnet means Studio's control-plane traffic technically transits a
route to the internet, even though the security group blocks inbound access —
this is an audit finding a stricter reviewer would flag, and it is why Lab 2
exists. Every teardown must delete the Domain's EFS home-directory filesystem
explicitly (`retention_policy { home_efs_file_system = "Delete" }`). The default
`Retain` setting is documented to survive `DeleteDomain` and leave its EFS mount
target pinning the subnet and security group, which would cause `terraform
destroy` to hang on those resources for several minutes before failing. Setting
`Delete` on every module in this codebase avoids that failure mode by design,
before `destroy` is ever run.

#### What would cause you to revisit this decision
Adding a second IAM role that needs to write to `raw/` or `processed/` (the
DataEngineer role in Lab 2) is the trigger to move Studio into a private subnet
with NAT egress, since a real data-ingestion role handling customer PII belongs
behind stricter network isolation than "public subnet, VPC-only security group."

### Alternative Considered

An alternative was one shared IAM role for all data-stage access, with
prefix-level control deferred to bucket policies instead of the execution role's
own inline policy. This was rejected because SageMaker's execution role is the
actual identity every API call runs as — a bucket policy would need to
special-case which *calling principal* gets which prefix, duplicating the same
logic the IAM policy already expresses more directly, and would leave the failure
mode (an ML engineer accidentally overwriting `raw/`) enforced by a second,
easy-to-drift document instead of the role definition itself.

### AWS Service Selection

- **Networking isolation model**: A single VPC with one public subnet and a
  VPC-scoped security group, chosen because Lab 1 has exactly one role and one
  workload — full private-subnet isolation is deferred until a second role
  exists to justify the NAT gateway cost.
- **Storage design**: One versioned, encrypted S3 bucket with lifecycle-stage
  prefixes, chosen so storage structure never needs to change as new roles are
  added — only IAM policy statements do.
- **Identity model**: A single least-privilege IAM role scoped by S3 prefix and
  SageMaker resource ARN, chosen so access boundaries are enforced structurally
  rather than by convention.
- **ML development environment**: SageMaker Studio in IAM auth mode, chosen as
  the shared IDE for all three NorthStar AI systems so every future lab builds on
  the same execution-role and network model rather than each system standing up
  its own notebook environment.
