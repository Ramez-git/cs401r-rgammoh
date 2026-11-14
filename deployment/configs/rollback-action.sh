#!/usr/bin/env bash
set -euo pipefail

aws sagemaker update-endpoint-weights-and-capacities \
  --region "${AWS_DEFAULT_REGION:-us-east-1}" \
  --endpoint-name northstar-churn-prod \
  --desired-weights-and-capacities \
  VariantName=champion,DesiredWeight=1 VariantName=canary,DesiredWeight=0
