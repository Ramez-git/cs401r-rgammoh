output "database_name" {
  description = "Raw data catalog database"
  value       = aws_glue_catalog_database.this.name
}
output "crawler_name" {
  description = "On-demand raw data crawler"
  value       = aws_glue_crawler.raw.name
}
output "job_names" {
  description = "Transform and feature job names"
  value       = { for key, job in aws_glue_job.jobs : key => job.name }
}
