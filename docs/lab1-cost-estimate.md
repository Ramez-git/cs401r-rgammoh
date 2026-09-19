# Lab 1 — Monthly Cost Estimate

Steady-state estimate for the `northstar-dev` platform (Part B infrastructure),
using [AWS Pricing Calculator](https://calculator.aws) rates for `us-east-1`.

| Component | Monthly Estimate | Key Assumptions | One Optimization |
|---|---|---|---|
| SageMaker Studio | $1.16 | 20 hrs/month of active `ml.t3.medium` KernelGateway usage at $0.0582/hr. JupyterServer app itself runs on the free `system` instance type; only the kernel gateway app is billed. | Attach a lifecycle configuration that auto-shuts-down idle kernels after 60 minutes. At an estimated 50% reduction in billed hours (10 hrs/month instead of 20), this drops the line to ~$0.58/month — a $0.58/month (50%) savings that compounds across every engineer once a second user profile is added in Lab 2. |
| S3 storage | $1.15 | 50 GB stored across all four prefixes (`raw/`, `processed/`, `features/`, `artifacts/`) at $0.023/GB-month, Standard storage class. | — |
| Internet Gateway | $0.10 | 10 GB/month of outbound data transfer (pulling ECR training images, Studio UI traffic) at $0.01/GB. IGW attachment itself carries no hourly charge. | — |
| DynamoDB (state lock) | $0.01 | On-demand billing mode; near-zero read/write volume — one lock acquired and released per `terraform apply`/`destroy`, at most a handful of times per month. | — |
| S3 state bucket | $0.01 | Terraform state file is under 50 KB; versioning keeps a handful of historical copies. Storage cost is effectively a rounding error at this scale. | — |
| **Total** | **$2.43** | | |

## Notes on assumptions

- These are **steady-state, single-engineer** estimates for the Lab 1 footprint
  only — one IAM role, one user profile, no training jobs or endpoints running
  yet. Actual training-job compute (e.g. `ml.m5.xlarge` for a churn model) and
  endpoint hosting costs are out of scope for this estimate and will be added
  when those workloads exist in later labs.
- SageMaker Studio cost assumes the engineer is not running training jobs
  *inside* the KernelGateway session — that would be billed separately as a
  SageMaker Training Job, not as Studio compute.
- The Internet Gateway itself has no hourly charge in this account; the $0.10
  line is purely the estimated data-transfer volume, not a resource fee.

## Quantified optimization

Adding a Studio lifecycle configuration that automatically shuts down idle
kernel gateway apps after 60 minutes of inactivity is the single highest-leverage
change available at this scale: it is a one-time Terraform change (a
`lifecycle_config_arns` reference on the domain's `kernel_gateway_app_settings`)
that is expected to cut billed Studio hours by roughly half, saving an estimated
**$0.58/month** today. That savings scales linearly with headcount — once
Lab 2 adds a DataEngineer role and a second user profile, the same idle-shutdown
policy is expected to save roughly $1.16/month across two engineers instead of
one, for zero additional infrastructure cost.
