# Lab 2 verification results

Deployed and initially verified September 30, 2026 (America/Denver), in AWS
us-east-1. Submission checks and the complete offline snapshot were reverified
October 2, 2026.

| Check | Observed result | Evidence |
|---|---|---|
| AWS deployment | 39 resources created; follow-up script and configuration updates applied | [Apply log](lab2-extend-output.txt) |
| Supplied verifier | 47 passed, 0 failed | [Verification log](lab2-verify-output.txt) |
| LocalStack | Three IAM roles, public/private subnets, no NAT | [LocalStack log](lab2-localstack-output.txt) |
| Local Spark tests | Edge cases and full sample passed | [Data-test log](lab2-local-data-tests.txt) |
| Terraform | Formatting and both environment configurations valid | [Validation log](lab2-terraform-validation.txt) |
| Transform | SUCCEEDED; 157,627 processed transactions | [Pipeline log](lab2-pipeline-output.txt) |
| Feature engineering | SUCCEEDED; 9,999 customer records; 22.0% churn | [Verification log](lab2-verify-output.txt) |
| Online Feature Store | Sample customer returns all 16 fields | [Pipeline log](lab2-pipeline-output.txt) |
| Offline Feature Store | All 9,999 customers and feature values match; 54 Parquet files | [Offline verification](lab2-offline-verification.txt) |

The final Terraform plan reported no changes. Credential scans of Git history
and the current tracked/untracked non-ignored files found no credentials.

## Submission

The grading tag is `lab2-submit`.
Repository: `https://github.com/Ramez-git/cs401r-rgammoh`.

After Canvas submission, the AWS stack was destroyed on October 2, 2026.
[Teardown evidence](lab2-destroy-output.txt) records Terraform destruction and
the cleanup script's final checks. Independent AWS API checks confirmed no
remaining NAT gateways, Elastic IPs, SageMaker domains, feature groups, EFS
filesystems, Glue jobs, NorthStar VPCs, Glue databases, or lineage entities.
Terraform state contains no remaining resources. The remote-state bucket is
intentionally retained for Lab 3. This evidence is committed on `main`; the
`lab2-submit` tag remains on the previously verified implementation.

## Windows portability notes

- `scripts/validate-local.ps1` avoids the failing awslocal wrapper by using the
  AWS CLI at the LocalStack endpoint with temporary dummy credentials.
- The verifier's Python tally file explicitly uses LF endings. No rubric checks
  were removed or weakened.
- SageMaker's returned empty `studio_web_portal_settings` block is declared in
  Terraform so repeated plans remain clean.
