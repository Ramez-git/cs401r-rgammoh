locals {
  fractional_features = [
    "event_time", "days_since_last_purchase", "customer_tenure_days",
    "purchase_frequency_30d", "purchase_frequency_90d", "purchase_frequency_180d",
    "avg_order_value", "total_spend_90d", "total_lifetime_value",
    "avg_basket_size_6m", "category_diversity_score", "online_to_store_ratio", "churn_risk_score"
  ]
  definitions = merge(
    { for name in local.fractional_features : name => "Fractional" },
    { customer_id = "String", loyalty_tier = "String", churn_label = "Integral" }
  )
}

resource "aws_sagemaker_feature_group" "customers" {
  feature_group_name             = "${var.project}-${var.environment}-customer-features"
  record_identifier_feature_name = "customer_id"
  event_time_feature_name        = "event_time"
  role_arn                       = var.execution_role_arn
  online_store_config { enable_online_store = true }
  offline_store_config {
    s3_storage_config { s3_uri = "s3://${var.bucket_name}/features/offline-store/" }
  }
  dynamic "feature_definition" {
    for_each = local.definitions
    content {
      feature_name = feature_definition.key
      feature_type = feature_definition.value
    }
  }
}
