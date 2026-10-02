data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  bucket_arn        = "arn:aws:s3:::${var.project}-${var.environment}-data-${data.aws_caller_identity.current.account_id}"
  feature_group_arn = "arn:aws:sagemaker:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:feature-group/${var.project}-${var.environment}-customer-features"
}

resource "aws_iam_role" "data_engineer" {
  name = "${var.project}-${var.environment}-DataEngineer"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = {
      Service = ["glue.amazonaws.com", "lambda.amazonaws.com", "sagemaker.amazonaws.com"]
    } }]
  })
}

resource "aws_iam_role_policy" "data_engineer" {
  name = "${var.project}-${var.environment}-DataEngineerPolicy"
  role = aws_iam_role.data_engineer.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["glue:*"], Resource = "*" },
      { Effect = "Allow", Action = ["ec2:CreateNetworkInterface", "ec2:DeleteNetworkInterface", "ec2:DescribeNetworkInterfaces", "ec2:DescribeVpcEndpoints", "ec2:DescribeRouteTables", "ec2:DescribeSubnets", "ec2:DescribeSecurityGroups", "ec2:DescribeVpcAttribute"], Resource = "*" },
      { Effect = "Allow", Action = ["ec2:CreateTags", "ec2:DeleteTags"], Resource = "arn:aws:ec2:*:*:network-interface/*" },
      { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"], Resource = [for prefix in ["raw", "processed", "features"] : "${local.bucket_arn}/${prefix}/*"] },
      { Effect = "Allow", Action = ["s3:GetObject"], Resource = "${local.bucket_arn}/artifacts/glue/*" },
      { Effect = "Allow", Action = ["s3:GetBucketLocation", "s3:GetBucketAcl", "s3:ListBucket"], Resource = local.bucket_arn },
      { Effect = "Allow", Action = ["s3:PutObjectAcl"], Resource = "${local.bucket_arn}/features/*" },
      { Effect = "Allow", Action = ["sagemaker:PutRecord", "sagemaker:CreateFeatureGroup", "sagemaker:DescribeFeatureGroup"], Resource = local.feature_group_arn },
      { Effect = "Allow", Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"], Resource = ["arn:aws:logs:*:*:log-group:/aws-glue/*", "arn:aws:logs:*:*:log-group:/aws/lambda/${var.project}-${var.environment}-*"] },
      { Effect = "Allow", Action = ["cloudwatch:PutMetricData"], Resource = "*", Condition = { StringEquals = { "cloudwatch:namespace" = "Glue" } } }
    ]
  })
}

resource "aws_iam_role" "model_monitor" {
  name               = "${var.project}-${var.environment}-ModelMonitor"
  assume_role_policy = data.aws_iam_policy_document.trust.json
}

resource "aws_iam_role_policy" "model_monitor" {
  name = "${var.project}-${var.environment}-ModelMonitorPolicy"
  role = aws_iam_role.model_monitor.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["cloudwatch:PutMetricData", "cloudwatch:GetMetricStatistics", "cloudwatch:PutMetricAlarm", "cloudwatch:DescribeAlarms"], Resource = "*" },
      { Effect = "Allow", Action = ["sagemaker:ListProcessingJobs", "sagemaker:DescribeProcessingJob"], Resource = "*" },
      { Effect = "Allow", Action = ["s3:GetObject"], Resource = "${local.bucket_arn}/artifacts/*" },
      { Effect = "Allow", Action = ["s3:GetBucketLocation"], Resource = local.bucket_arn },
      { Effect = "Allow", Action = ["s3:ListBucket"], Resource = local.bucket_arn, Condition = { StringLike = { "s3:prefix" = ["artifacts/", "artifacts/*"] } } },
      { Effect = "Allow", Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"], Resource = "arn:aws:logs:*:*:log-group:/aws/sagemaker/*" }
    ]
  })
}

resource "aws_iam_role_policy" "ml_feature_read" {
  name = "${var.project}-${var.environment}-FeatureRead"
  role = aws_iam_role.ml_engineer.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["sagemaker:GetRecord", "sagemaker:BatchGetRecord", "sagemaker:DescribeFeatureGroup"], Resource = local.feature_group_arn }]
  })
}

output "data_engineer_role_arn" {
  description = "DataEngineer execution role for Glue and Feature Store"
  value       = aws_iam_role.data_engineer.arn
  depends_on  = [aws_iam_role_policy.data_engineer]
}

output "model_monitor_role_arn" {
  description = "Read-only model observer role"
  value       = aws_iam_role.model_monitor.arn
}
