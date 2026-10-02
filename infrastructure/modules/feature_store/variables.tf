variable "project" {
  description = "Project resource name prefix"
  type        = string
}
variable "environment" {
  description = "Deployment environment"
  type        = string
}
variable "execution_role_arn" {
  description = "DataEngineer role trusted by SageMaker"
  type        = string
}
variable "bucket_name" {
  description = "Data bucket backing the offline store"
  type        = string
}
