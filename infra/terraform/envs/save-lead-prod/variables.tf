variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "europe-southwest1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "save-lead-mcp"
}

variable "container_image" {
  description = "Container image URL"
  type        = string
}

variable "cloudrun_cpu" {
  description = "CPU limit for Cloud Run"
  type        = string
  default     = "1"
}

variable "cloudrun_memory" {
  description = "Memory limit for Cloud Run"
  type        = string
  default     = "512Mi"
}

variable "cloudrun_min_instances" {
  description = "Minimum number of Cloud Run instances"
  type        = number
  default     = 0
}

variable "cloudrun_max_instances" {
  description = "Maximum number of Cloud Run instances"
  type        = number
  default     = 5
}

variable "contact_to_email" {
  description = "Recipient email for lead notifications"
  type        = string
  default     = "founder@example.com"
}

variable "contact_from_email" {
  description = "Sender email for lead notifications"
  type        = string
  default     = "bot@verifieddomain.com"
}

variable "resend_api_key_secret_name" {
  description = "Secret Manager secret name for Resend API Key"
  type        = string
  default     = "unibot-prod-resend-api-key"
}
