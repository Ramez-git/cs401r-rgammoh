# NorthStar churn deployment plan

## 1. Deployment strategy and rationale

NorthStar ranks active customers by their 90-day churn risk. Scores are due by Monday at 6 a.m. Eastern for the weekly retention campaign. A scheduled batch job suits this weekly workload because the retention team needs the full ranking before the campaign starts. This lab uses a SageMaker real-time endpoint to test traffic routing and rollback and collect inference records for Lab 6. Requests use synthetic customer features, and the scores are used only for the lab. Model Registry v2 serves as champion and v3 starts at 10% of requests on one shared endpoint. The offer generator stays in staging.

## 2. Pre-deployment checklist

Work from the repository root using Bash, AWS CLI v2, Terraform, and Python with Boto3. Set the region and verify the lab account and package approvals.

```bash
export AWS_DEFAULT_REGION=us-east-1 AWS_PAGER=''
aws sts get-caller-identity
aws sagemaker list-model-packages --model-package-group-name northstar-churn-models
terraform -chdir=infrastructure/environments/dev init
terraform -chdir=infrastructure/environments/dev plan \
  -target=module.iam.aws_iam_policy.ml_engineer \
  -target=module.storage.aws_s3_bucket_lifecycle_configuration.data \
  -out=lab5-capture.tfplan
```

Apply a reviewed plan containing the capture-only IAM grant and the S3 lifecycle update. Confirm the capture rule shows current expiration at seven days and noncurrent expiration after one day.

```bash
terraform -chdir=infrastructure/environments/dev apply lab5-capture.tfplan
aws s3api get-bucket-lifecycle-configuration --bucket northstar-dev-data-701145280839 \
  --query "Rules[?ID=='expire-datacapture'].[Expiration.Days,NoncurrentVersionExpiration.NoncurrentDays]" \
  --output text
```

The model owner approved v3 on November 13, 2026 (Mountain time), for the synthetic canary only. The reviewed holdout AUC was 0.7846, matching v2. Top-decile precision was 71.7% and recall was 32.6%, against gates of 50% and 25%. The paired 95% AUC-lift interval over recency was [0.0434, 0.0824]. The model files matched byte for byte. Gold recall was 13.5% versus Bronze at 44.9%, a 31.4-point gap above the 10-point review threshold. Require a separate fairness and release review before any customer use.

Check the instance quota and run the secret scan. The deployment script checks that the lab account has no existing inference resources because the teardown script deletes these resources across the region. It reads the configuration files from deployment/configs/, sends the sample row with 11 features and no header, and saves the deployment evidence.

```bash
aws service-quotas get-service-quota --service-code sagemaker --quota-code L-614B09FD
bash scripts/check-secrets.sh
python -m pip install boto3
python scripts/deploy-lab5.py
```

## 3. Rollback criteria

The release operator rolls back if CloudWatch reports canary `AWS/SageMaker` `ModelLatency` p95 greater than **200,000 microseconds (200 ms)** for three consecutive one-minute periods. The deployment script checks the alarm every minute and runs the rollback command when the alarm trips or the observation period ends. During manual operation, run the same script and wait for `InService`.

```bash
bash deployment/configs/rollback-action.sh
aws sagemaker wait endpoint-in-service --endpoint-name northstar-churn-prod
```

Confirm champion weight 1 and canary weight 0, then send 100 untargeted invocations and require all 100 to reach the champion.

## 4. Monitoring window

Observe for 60 minutes instead of the 48 hours planned for a production canary. Begin with 200 untargeted calls, then continue probes every minute. Before ending the window, confirm that both variants have served requests, the requests succeeded, the latency alarm is OK, and both variants have written JSONL capture files. The champion can scale between one and two instances at a target of 1,000 invocations per instance per minute, with 60-second scale-out and 600-second scale-in cooldowns. The lab concludes with a rollback drill. Forty-eight hours would sample overnight traffic, upstream refreshes, and delayed errors. In production, track errors, input drift, labeled performance by loyalty tier, and whether the weekly scoring job meets its deadline.

## 5. Stakeholder notifications

At deployment start, the release operator tells ML Engineering, Model Monitoring, and the retention owner which versions are running, the traffic split, the monitoring period, and the limits on customer outreach. At promotion, send the same roles the latency and error results, approval record, and time of the change. On rollback, notify those roles and the on-call lead with the trigger, customer impact, restored weights, and verification result. Use the team incident channel for an unexpected rollback.

## 6. Post-deployment review

On the next business day, the operator, Data Engineering, Model Monitoring, and the retention owner review the evidence. Record the traffic split, alarm and rollback results, capture health, fairness follow-up, and action owners in the release ticket.

## 7. Resource cleanup

After evidence capture, delete the endpoint and wait for release. Then run `bash scripts/teardown-lab5.sh` to remove remaining policies, scaling targets, rollback alarms, endpoint configs, and model definitions. Confirm all six teardown checks report `OK` and section 6 reports zero. Keep the model registry and capture prefix for Lab 6. Run the secret scan on the final commit before pushing `main` and `lab5-submit`.
