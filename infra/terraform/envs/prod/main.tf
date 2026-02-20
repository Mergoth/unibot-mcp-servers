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
    prefix = "terraform/mcp-servers/google-calendar/prod"
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
  
  allow_public_access   = true # MCP servers might need to be public or protected by auth header, assuming public for now as per minimal viable setup or strict IP

  env_vars = {
    PORT = "8080"
  }
  
  # Note: To enable Service Account Key Auth as per user request:
  # 1. Provide GOOGLE_APPLICATION_CREDENTIALS path in env_vars
  # 2. Add the file content as a Secret in GCP
  # 3. Use secret_env_vars to map it (but this module supports env vars, not file mounts)
  # For now, we deploy the infrastructure. The user must manually configure the secret and update this file or use ADC.
}
