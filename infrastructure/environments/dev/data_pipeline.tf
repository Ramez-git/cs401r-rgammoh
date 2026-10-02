module "feature_store" {
  source             = "../../modules/feature_store"
  project            = var.project
  environment        = var.environment
  execution_role_arn = module.iam.data_engineer_role_arn
  bucket_name        = module.storage.bucket_name
  depends_on         = [module.storage]
}

module "glue" {
  source             = "../../modules/glue"
  project            = var.project
  environment        = var.environment
  bucket_name        = module.storage.bucket_name
  execution_role_arn = module.iam.data_engineer_role_arn
  feature_group_name = module.feature_store.feature_group_name
  vpc_id             = module.vpc.vpc_id
  private_subnet_id  = module.vpc.private_subnet_id
  availability_zone  = var.availability_zone
  region             = var.aws_region
}

output "feature_group_name" {
  description = "Customer Feature Store group"
  value       = module.feature_store.feature_group_name
}
