# Monitoring Module for GKE Auto-Heal Agent
# Sets up observability, logging, and alerting

# Log sink for Auto-Heal Agent logs
resource "google_logging_project_sink" "auto_heal_logs" {
  name        = "auto-heal-agent-logs"
  project     = var.project_id
  destination = "storage.googleapis.com/${google_storage_bucket.log_bucket.name}"

  filter = <<-EOT
    resource.type="k8s_container"
    resource.labels.namespace_name="${var.agent_namespace}"
    OR
    resource.type="gke_cluster"
    resource.labels.cluster_name="${var.cluster_name}"
  EOT

  unique_writer_identity = true
}

# Storage bucket for log archival
resource "google_storage_bucket" "log_bucket" {
  name          = "${var.project_id}-auto-heal-logs"
  project       = var.project_id
  location      = var.region
  force_destroy = var.force_destroy_bucket

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }

  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  versioning {
    enabled = true
  }

  dynamic "encryption" {
    for_each = var.kms_key_name != null ? [1] : []
    content {
      default_kms_key_name = var.kms_key_name
    }
  }
}

# Grant log sink permission to write to bucket
resource "google_storage_bucket_iam_member" "log_sink_writer" {
  bucket = google_storage_bucket.log_bucket.name
  role   = "roles/storage.objectCreator"
  member = google_logging_project_sink.auto_heal_logs.writer_identity
}

# Notification channel for alerts
resource "google_monitoring_notification_channel" "email" {
  count        = length(var.alert_email_addresses)
  display_name = "Email Notification ${count.index + 1}"
  type         = "email"
  project      = var.project_id

  labels = {
    email_address = var.alert_email_addresses[count.index]
  }
}

# Alert policy for agent health
resource "google_monitoring_alert_policy" "agent_health" {
  display_name = "Auto-Heal Agent Health"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "Agent Pod CPU Usage High"

    condition_threshold {
      filter          = "resource.type = \"k8s_container\" AND resource.labels.namespace_name = \"${var.agent_namespace}\" AND metric.type = \"kubernetes.io/container/cpu/core_usage_time\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = google_monitoring_notification_channel.email[*].id

  alert_strategy {
    auto_close = "1800s"
  }
}

# Custom log-based metric for error count (keeping for potential future use)
# resource "google_logging_metric" "error_count_metric" {
#   name   = "auto_heal_error_count_metric"
#   filter = "resource.type=\"k8s_container\" AND resource.labels.namespace_name=\"${var.agent_namespace}\" AND severity>=ERROR"
#   metric_descriptor {
#     metric_kind = "DELTA"
#     value_type  = "INT64"
#     unit        = "1"
#     display_name = "Auto-Heal Error Count"
#   }
# }

# Alert policy for high error rate using built-in logging metric
resource "google_monitoring_alert_policy" "high_error_rate" {
  display_name = "Auto-Heal Agent High Error Rate"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "High Error Rate in Logs"

    condition_threshold {
      filter          = "resource.type=\"k8s_container\" AND resource.labels.namespace_name=\"${var.agent_namespace}\" AND metric.type=\"logging.googleapis.com/log_entry_count\" AND metric.labels.severity=\"ERROR\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 5

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_DELTA"
      }
    }
  }

  notification_channels = google_monitoring_notification_channel.email[*].id

  alert_strategy {
    auto_close = "1800s"
  }
}

# # Alert policy for response time SLA - commented out as custom metric doesn't exist yet
# resource "google_monitoring_alert_policy" "response_time_sla" {
#   display_name = "Auto-Heal Agent Response Time SLA"
#   project      = var.project_id
#   combiner     = "OR"

#   conditions {
#     display_name = "Response Time > 90 seconds"

#     condition_threshold {
#       filter          = "resource.type=\"k8s_container\" AND resource.labels.namespace_name=\"${var.agent_namespace}\" AND metric.type=\"custom.googleapis.com/auto_heal/response_time\""
#       duration        = "300s"
#       comparison      = "COMPARISON_GT"
#       threshold_value = 90

#       aggregations {
#         alignment_period   = "60s"
#         per_series_aligner = "ALIGN_MEAN"
#       }
#     }
#   }

#   notification_channels = google_monitoring_notification_channel.email[*].id

#   alert_strategy {
#     auto_close = "1800s"
#   }
# }

# Dashboard for Auto-Heal Agent metrics
resource "google_monitoring_dashboard" "auto_heal_dashboard" {
  project        = var.project_id
  dashboard_json = jsonencode({
    displayName = "Auto-Heal Agent Dashboard"
    gridLayout = {
      columns = 2
      widgets = [
        {
          title = "Agent CPU Usage"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type=\"k8s_container\" AND resource.labels.namespace_name=\"${var.agent_namespace}\" AND metric.type=\"kubernetes.io/container/cpu/core_usage_time\""
                  aggregation = {
                    alignmentPeriod  = "60s"
                    perSeriesAligner = "ALIGN_RATE"
                  }
                }
              }
            }]
            timeshiftDuration = "0s"
            yAxis = {
              label = "CPU Cores"
              scale = "LINEAR"
            }
          }
        },
        {
          title = "Agent Memory Usage"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type=\"k8s_container\" AND resource.labels.namespace_name=\"${var.agent_namespace}\" AND metric.type=\"kubernetes.io/container/memory/used_bytes\""
                  aggregation = {
                    alignmentPeriod  = "60s"
                    perSeriesAligner = "ALIGN_MEAN"
                  }
                }
              }
            }]
            timeshiftDuration = "0s"
            yAxis = {
              label = "Memory (bytes)"
              scale = "LINEAR"
            }
          }
        },
        {
          title = "Error Logs"
          logsPanel = {
            filter = "resource.type=\"k8s_container\" AND resource.labels.namespace_name=\"${var.agent_namespace}\" AND severity>=ERROR"
          }
        },
        {
          title = "Agent Pod Count"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type=\"k8s_pod\" AND resource.labels.namespace_name=\"${var.agent_namespace}\" AND metric.type=\"kubernetes.io/pod/uptime\""
                  aggregation = {
                    alignmentPeriod    = "60s"
                    crossSeriesReducer = "REDUCE_COUNT"
                    perSeriesAligner   = "ALIGN_MEAN"
                  }
                }
              }
            }]
            timeshiftDuration = "0s"
            yAxis = {
              label = "Pod Count"
              scale = "LINEAR"
            }
          }
        }
      ]
    }
  })
}