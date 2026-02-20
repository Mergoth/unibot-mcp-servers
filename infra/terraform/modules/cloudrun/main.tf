resource "google_cloud_run_v2_service" "api" {
  name                = "${var.app_name}-${var.environment}"
  location            = var.region
  project             = var.project_id
  deletion_protection = var.deletion_protection

  template {
    service_account = var.service_account_email

    containers {
      image = var.container_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = var.cpu_limit
          memory = var.memory_limit
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      # Environment variables (plain text)
      dynamic "env" {
        for_each = var.env_vars
        content {
          name  = env.key
          value = env.value
        }
      }

      # Environment variables (from Secret Manager)
      dynamic "env" {
        for_each = var.secret_env_vars
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }

      # Startup probe
      startup_probe {
        http_get {
          path = "/sse"  # Changed from /health because /sse is a GET endpoint on the MCP server
          port = 8080
        }
        initial_delay_seconds = 10
        timeout_seconds       = 3
        period_seconds        = 10
        failure_threshold     = 3
      }

      # Liveness probe
      liveness_probe {
        http_get {
          path = "/sse"  # Changed from /health
          port = 8080
        }
        initial_delay_seconds = 30
        timeout_seconds       = 3
        period_seconds        = 30
        failure_threshold     = 3
      }
    }

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    timeout = "${var.request_timeout}s"
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}

# IAM policy to allow public access (for dev/prod if enabled)
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  count = var.allow_public_access ? 1 : 0

  project  = google_cloud_run_v2_service.api.project
  location = google_cloud_run_v2_service.api.location
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
