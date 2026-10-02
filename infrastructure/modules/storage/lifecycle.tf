variable "enable_lifecycle_rules" {
  description = "Enable Lab 2 retention rules; disable for LocalStack"
  type        = bool
  default     = true
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  count      = var.enable_lifecycle_rules ? 1 : 0
  bucket     = aws_s3_bucket.data.id
  depends_on = [aws_s3_bucket_versioning.data]

  rule {
    id     = "expire-raw-data"
    status = "Enabled"
    filter { prefix = "raw/" }
    expiration { days = 90 }
  }
  dynamic "rule" {
    for_each = {
      expire-raw-versions       = { prefix = "raw/", days = 30 }
      expire-processed-versions = { prefix = "processed/", days = 30 }
      expire-feature-versions   = { prefix = "features/", days = 60 }
    }
    content {
      id     = rule.key
      status = "Enabled"
      filter { prefix = rule.value.prefix }
      noncurrent_version_expiration { noncurrent_days = rule.value.days }
    }
  }
  rule {
    id     = "expire-datacapture"
    status = "Enabled"
    filter { prefix = "datacapture/" }
    expiration { days = 7 }
  }
}
