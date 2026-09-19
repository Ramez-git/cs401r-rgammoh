# ── modules/iam ──────────────────────────────────────────────────────────────
# MLEngineer role, trusted by sagemaker.amazonaws.com, with the same
# least-privilege inline-policy shape built manually in Part A: full access to
# SageMaker training/endpoint/MLflow/model-registry actions and Studio
# self-service, read/write on only the artifacts/ and features/ S3 prefixes,
# CloudWatch Logs write, and ECR read.

data "aws_iam_policy_document" "trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["sagemaker.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ml_engineer" {
  name               = "${var.project}-${var.environment}-MLEngineer"
  assume_role_policy = data.aws_iam_policy_document.trust.json
}

data "aws_iam_policy_document" "ml_engineer" {
  statement {
    sid    = "SageMakerCore"
    effect = "Allow"
    actions = [
      "sagemaker:CreateTrainingJob", "sagemaker:DescribeTrainingJob", "sagemaker:StopTrainingJob",
      "sagemaker:CreateEndpoint", "sagemaker:DescribeEndpoint", "sagemaker:DeleteEndpoint",
      "sagemaker:CreateEndpointConfig", "sagemaker:DeleteEndpointConfig",
      "sagemaker:CreateMlflowApp", "sagemaker:DescribeMlflowApp", "sagemaker:ListMlflowApps",
      "sagemaker:CreatePresignedMlflowAppUrl",
      "sagemaker:CreateModelPackage", "sagemaker:DescribeModelPackage", "sagemaker:ListModelPackages",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "StudioSelfService"
    effect = "Allow"
    actions = [
      "sagemaker:DescribeDomain", "sagemaker:ListDomains",
      "sagemaker:DescribeUserProfile", "sagemaker:ListUserProfiles",
      "sagemaker:DescribeSpace", "sagemaker:ListSpaces", "sagemaker:CreateSpace",
      "sagemaker:UpdateSpace", "sagemaker:DeleteSpace",
      "sagemaker:DescribeApp", "sagemaker:ListApps", "sagemaker:CreateApp", "sagemaker:DeleteApp",
      "sagemaker:CreatePresignedDomainUrl", "sagemaker:AddTags", "sagemaker:DeleteTags",
    ]
    resources = [
      "arn:aws:sagemaker:*:*:domain/*",
      "arn:aws:sagemaker:*:*:user-profile/*",
      "arn:aws:sagemaker:*:*:space/*",
      "arn:aws:sagemaker:*:*:app/*",
    ]
  }

  statement {
    sid    = "S3ArtifactsAndFeatures"
    effect = "Allow"
    actions = [
      "s3:GetObject", "s3:PutObject", "s3:DeleteObject",
    ]
    resources = [
      "arn:aws:s3:::${var.project}-${var.environment}-data-*/artifacts/*",
      "arn:aws:s3:::${var.project}-${var.environment}-data-*/features/*",
    ]
  }

  statement {
    sid       = "S3BucketList"
    effect    = "Allow"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = ["arn:aws:s3:::${var.project}-${var.environment}-data-*"]
  }

  statement {
    sid       = "CloudWatchLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:*:*:log-group:/aws/sagemaker/*"]
  }

  statement {
    sid       = "ECRRead"
    effect    = "Allow"
    actions   = ["ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage", "ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "ml_engineer" {
  name        = "${var.project}-${var.environment}-MLEngineerPolicy"
  description = "Least-privilege permissions for the MLEngineer SageMaker execution role"
  policy      = data.aws_iam_policy_document.ml_engineer.json
}

resource "aws_iam_role_policy_attachment" "ml_engineer" {
  role       = aws_iam_role.ml_engineer.name
  policy_arn = aws_iam_policy.ml_engineer.arn
}
