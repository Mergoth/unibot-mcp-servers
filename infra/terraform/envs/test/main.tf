terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  backend "gcs" {
    bucket = "unibot-terraform-state-bucket"
    prefix = "terraform/mcp-servers/google-calendar/test"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# IAM Module
module "iam" {
  source = "../../modules/iam"

  project_id  = var.project_id
  app_name    = var.app_name
  environment = var.environment
}

# Cloud Run Module
module "cloudrun" {
  source = "../../modules/cloudrun"

  project_id            = var.project_id
  region                = var.region
  app_name              = var.app_name
  environment           = var.environment
  container_image       = var.container_image
  service_account_email = module.iam.service_account_email

  cpu_limit             = var.cloudrun_cpu
  memory_limit          = var.cloudrun_memory
  min_instances         = var.cloudrun_min_instances
  max_instances         = var.cloudrun_max_instances
  
  allow_public_access   = true # MCP server relies on IAM auth

  env_vars = {}
}
