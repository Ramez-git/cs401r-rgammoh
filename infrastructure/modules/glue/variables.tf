variable "project" {
  description = "Project resource name prefix"
  type        = string
}
variable "environment" {
  description = "Deployment environment"
  type        = string
}
variable "bucket_name" {
  description = "Data bucket containing raw, processed, features and scripts"
  type        = string
}
variable "execution_role_arn" {
  description = "DataEngineer Glue execution role"
  type        = string
}
variable "feature_group_name" {
  description = "Destination Feature Store group"
  type        = string
}
variable "vpc_id" {
  description = "VPC containing Glue workers"
  type        = string
}
variable "private_subnet_id" {
  description = "Private subnet with NAT routing"
  type        = string
}
variable "availability_zone" {
  description = "Availability zone containing the private subnet"
  type        = string
}
variable "region" {
  description = "AWS region for Feature Store calls"
  type        = string
}
