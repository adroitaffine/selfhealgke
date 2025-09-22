# Outputs for Monitoring Module

output "log_bucket_name" {
  description = "Name of the log storage bucket"
  value       = google_storage_bucket.log_bucket.name
}

output "log_sink_name" {
  description = "Name of the log sink"
  value       = google_logging_project_sink.auto_heal_logs.name
}

output "notification_channel_ids" {
  description = "IDs of the notification channels"
  value       = google_monitoring_notification_channel.email[*].id
}

output "dashboard_id" {
  description = "ID of the monitoring dashboard"
  value       = google_monitoring_dashboard.auto_heal_dashboard.id
}