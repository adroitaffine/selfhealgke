# IAM Module for GKE Auto-Heal Agent
# Creates additional IAM roles and bindings with minimal permissions

# Custom IAM role for Auto-Heal Agent with minimal permissions
resource "google_project_iam_custom_role" "auto_heal_agent_role" {
  role_id     = "autoHealAgent"
  title       = "Auto-Heal Agent Role"
  description = "Custom role for Auto-Heal Agent with minimal required permissions"
  project     = var.project_id

  permissions = [
    # Logging permissions
    "logging.logEntries.list",
    
    # Cloud Trace permissions
    "cloudtrace.traces.get",
    "cloudtrace.traces.list",
    
    # Container/GKE permissions
    "container.deployments.get",
    "container.deployments.list",
    "container.deployments.update",
    "container.pods.get",
    "container.pods.list",
    "container.replicaSets.get",
    "container.replicaSets.list",
    
    # Vertex AI permissions - using valid permissions
    "aiplatform.endpoints.predict",
    
    # Monitoring permissions
    "monitoring.timeSeries.list",
    "monitoring.metricDescriptors.list",
  ]
}

# Service account for Terraform operations
resource "google_service_account" "terraform_sa" {
  account_id   = "terraform-auto-heal"
  display_name = "Terraform Service Account for Auto-Heal"
  description  = "Service account used by Terraform for Auto-Heal infrastructure"
  project      = var.project_id
}

# Terraform service account permissions
resource "google_project_iam_member" "terraform_editor" {
  count   = var.grant_terraform_permissions ? 1 : 0
  project = var.project_id
  role    = "roles/editor"
  member  = "serviceAccount:${google_service_account.terraform_sa.email}"
}

resource "google_project_iam_member" "terraform_security_admin" {
  count   = var.grant_terraform_permissions ? 1 : 0
  project = var.project_id
  role    = "roles/iam.securityAdmin"
  member  = "serviceAccount:${google_service_account.terraform_sa.email}"
}

# Service account for monitoring and alerting
resource "google_service_account" "monitoring_sa" {
  account_id   = "auto-heal-monitoring"
  display_name = "Auto-Heal Monitoring Service Account"
  description  = "Service account for monitoring and alerting components"
  project      = var.project_id
}

# Monitoring service account permissions
resource "google_project_iam_member" "monitoring_viewer" {
  project = var.project_id
  role    = "roles/monitoring.viewer"
  member  = "serviceAccount:${google_service_account.monitoring_sa.email}"
}

resource "google_project_iam_member" "monitoring_alerting" {
  project = var.project_id
  role    = "roles/monitoring.alertPolicyEditor"
  member  = "serviceAccount:${google_service_account.monitoring_sa.email}"
}

resource "google_project_iam_member" "monitoring_notification" {
  project = var.project_id
  role    = "roles/monitoring.notificationChannelEditor"
  member  = "serviceAccount:${google_service_account.monitoring_sa.email}"
}

# Audit logging configuration
resource "google_project_iam_audit_config" "audit_config" {
  project = var.project_id
  service = "allServices"

  audit_log_config {
    log_type = "ADMIN_READ"
  }

  audit_log_config {
    log_type = "DATA_READ"
  }

  audit_log_config {
    log_type = "DATA_WRITE"
  }
}

# Organization policy constraints (if organization is provided)
resource "google_project_organization_policy" "require_shielded_vm" {
  count      = var.organization_id != "" ? 1 : 0
  project    = var.project_id
  constraint = "compute.requireShieldedVm"

  boolean_policy {
    enforced = true
  }
}

resource "google_project_organization_policy" "restrict_vm_external_ips" {
  count      = var.organization_id != "" ? 1 : 0
  project    = var.project_id
  constraint = "compute.vmExternalIpAccess"

  list_policy {
    deny {
      all = true
    }
  }
}