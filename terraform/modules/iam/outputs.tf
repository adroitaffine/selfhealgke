# Outputs for IAM Module

output "auto_heal_agent_custom_role_id" {
  description = "ID of the custom Auto-Heal Agent role"
  value       = google_project_iam_custom_role.auto_heal_agent_role.role_id
}

output "terraform_service_account_email" {
  description = "Email of the Terraform service account"
  value       = google_service_account.terraform_sa.email
}

output "monitoring_service_account_email" {
  description = "Email of the monitoring service account"
  value       = google_service_account.monitoring_sa.email
}