# ── modules/sagemaker ────────────────────────────────────────────────────────
# Domain + user profile, matching the manual Part A build: IAM auth, the
# MLEngineer role as default execution role, notebook output sharing
# disabled, and retention_policy set to Delete so `terraform destroy` doesn't
# hang on the Studio EFS volume pinning the subnet/security group.

resource "aws_sagemaker_domain" "this" {
  domain_name = "${var.project}-${var.environment}-domain"
  auth_mode   = "IAM"
  vpc_id      = var.vpc_id
  subnet_ids  = var.subnet_ids

  app_network_access_type = "VpcOnly"

  default_user_settings {
    execution_role  = var.execution_role_arn
    security_groups = var.security_group_ids

    sharing_settings {
      notebook_output_option = "Disabled"
    }

    jupyter_server_app_settings {
      default_resource_spec {
        instance_type = "system"
      }
    }

    kernel_gateway_app_settings {
      default_resource_spec {
        instance_type = var.instance_type
      }
    }
  }

  retention_policy {
    home_efs_file_system = "Delete"
  }

  tags = {
    Name = "${var.project}-${var.environment}-domain"
  }
}

resource "aws_sagemaker_user_profile" "ml_engineer" {
  domain_id         = aws_sagemaker_domain.this.id
  user_profile_name = "MLEngineer"

  user_settings {
    execution_role = var.execution_role_arn
  }

  tags = {
    Name = "${var.project}-${var.environment}-MLEngineer-profile"
  }
}
