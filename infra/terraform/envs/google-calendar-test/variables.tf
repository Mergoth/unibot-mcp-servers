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
  default     = "test"
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "google-calendar-mcp"
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
  default     = 2
}
