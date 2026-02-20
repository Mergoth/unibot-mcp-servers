# Service Account for Cloud Run
resource "google_service_account" "app" {
  account_id   = "${var.app_name}-${var.environment}"
  display_name = "Service account for ${var.app_name} ${var.environment}"
  description  = "Used by Cloud Run service to access GCP resources"
}

# Basic IAM roles for the service account
resource "google_project_iam_member" "app_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.app.email}"
}

resource "google_project_iam_member" "app_metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.app.email}"
}

resource "google_project_iam_member" "app_trace_agent" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.app.email}"
}

resource "google_project_iam_member" "app_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.app.email}"
}
