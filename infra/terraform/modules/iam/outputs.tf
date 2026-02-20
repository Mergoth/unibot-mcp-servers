output "service_account_email" {
  description = "Email of the service account"
  value       = google_service_account.app.email
}

output "service_account_id" {
  description = "ID of the service account"
  value       = google_service_account.app.id
}

output "service_account_name" {
  description = "Name of the service account"
  value       = google_service_account.app.name
}
