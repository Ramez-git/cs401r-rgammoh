locals {
  prefix = "${var.project}-${var.environment}"
  scripts = {
    transform        = "transform.py"
    feature-engineer = "feature_engineer.py"
  }
}

resource "aws_glue_catalog_database" "this" {
  name = replace("${var.project}_${var.environment}", "-", "_")
}

resource "aws_glue_crawler" "raw" {
  name          = "${local.prefix}-raw-crawler"
  database_name = aws_glue_catalog_database.this.name
  role          = var.execution_role_arn
  s3_target { path = "s3://${var.bucket_name}/raw/customers/" }
}

resource "aws_security_group" "glue" {
  name        = "${local.prefix}-glue-sg"
  description = "Glue worker communication and outbound AWS API access"
  vpc_id      = var.vpc_id
  ingress {
    description = "Glue workers communicate with each other"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_glue_connection" "private" {
  name            = "${local.prefix}-private-network"
  connection_type = "NETWORK"
  physical_connection_requirements {
    subnet_id              = var.private_subnet_id
    security_group_id_list = [aws_security_group.glue.id]
    availability_zone      = var.availability_zone
  }
}

resource "aws_s3_object" "scripts" {
  for_each    = local.scripts
  bucket      = var.bucket_name
  key         = "artifacts/glue/${each.value}"
  source      = "${path.module}/../../../glue-scripts/${each.value}"
  source_hash = filemd5("${path.module}/../../../glue-scripts/${each.value}")
}

resource "aws_glue_job" "jobs" {
  for_each          = local.scripts
  name              = "${local.prefix}-${each.key}"
  role_arn          = var.execution_role_arn
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2
  timeout           = 30
  max_retries       = 0
  connections       = [aws_glue_connection.private.name]
  execution_property { max_concurrent_runs = 1 }
  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${var.bucket_name}/${aws_s3_object.scripts[each.key].key}"
  }
  default_arguments = merge({
    "--job-language"                     = "python"
    "--job-bookmark-option"              = "job-bookmark-disable"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-metrics"                   = "true"
    "--TempDir"                          = "s3://${var.bucket_name}/processed/glue-temp/"
    "--conf"                             = "spark.sql.ansi.enabled=false --conf spark.sql.legacy.timeParserPolicy=CORRECTED"
    }, each.key == "transform" ? {
    "--database_name" = aws_glue_catalog_database.this.name
    "--table_name"    = "customers"
    "--output_path"   = "s3://${var.bucket_name}/processed/customers/"
    } : {
    "--input_path"         = "s3://${var.bucket_name}/processed/customers/"
    "--output_path"        = "s3://${var.bucket_name}/features/customers/"
    "--feature_group_name" = var.feature_group_name
    "--region"             = var.region
  })
}
