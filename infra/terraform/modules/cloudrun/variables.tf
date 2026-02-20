variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region for Cloud Run service"
  type        = string
}

variable "app_name" {
  description = "Application name"
  type        = string
}

variable "environment" {
  description = "Environment name (dev/prod)"
  type        = string
}

variable "container_image" {
  description = "Container image URL (e.g., gcr.io/project/image:tag)"
  type        = string
}

variable "service_account_email" {
  description = "Service account email for Cloud Run"
  type        = string
}

variable "cpu_limit" {
  description = "CPU limit (e.g., '1', '2', '4')"
  type        = string
  default     = "1"
}

variable "memory_limit" {
  description = "Memory limit (e.g., '512Mi', '1Gi', '2Gi')"
  type        = string
  default     = "512Mi"
}

variable "min_instances" {
  description = "Minimum number of instances"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of instances"
  type        = number
  default     = 10
}

variable "request_timeout" {
  description = "Request timeout in seconds"
  type        = number
  default     = 300
}

variable "allow_public_access" {
  description = "Allow public access (allUsers invoker)"
  type        = bool
  default     = false
}

variable "env_vars" {
  description = "Environment variables for the container"
  type        = map(string)
  default     = {}
}

variable "deletion_protection" {
  description = "Prevent accidental deletion of the service (recommended: true for prod, false for dev)"
  type        = bool
  default     = false
}

variable "secret_env_vars" {
  description = "Environment variables from Secret Manager (map of env_var_name to secret_name)"
  type        = map(string)
  default     = {}
}
