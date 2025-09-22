# Service Accounts and IAM Configuration

# GKE Node Service Account
resource "google_service_account" "gke_node_sa" {
  account_id   = "${var.cluster_name}-node-sa"
  display_name = "GKE Node Service Account for ${var.cluster_name}"
  description  = "Service account for GKE nodes in ${var.cluster_name} cluster"
  project      = var.project_id
}

# Auto-Heal Agent Service Account
resource "google_service_account" "auto_heal_agent_sa" {
  account_id   = "${var.cluster_name}-agent-sa"
  display_name = "Auto-Heal Agent Service Account"
  description  = "Service account for Auto-Heal Agent operations"
  project      = var.project_id
}

# GKE Node Service Account IAM Bindings
resource "google_project_iam_member" "gke_node_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.gke_node_sa.email}"
}

resource "google_project_iam_member" "gke_node_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.gke_node_sa.email}"
}

resource "google_project_iam_member" "gke_node_monitoring_viewer" {
  project = var.project_id
  role    = "roles/monitoring.viewer"
  member  = "serviceAccount:${google_service_account.gke_node_sa.email}"
}

resource "google_project_iam_member" "gke_node_registry" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.gke_node_sa.email}"
}

# Auto-Heal Agent IAM Bindings (Minimal Permissions)
resource "google_project_iam_member" "agent_logging_viewer" {
  project = var.project_id
  role    = "roles/logging.viewer"
  member  = "serviceAccount:${google_service_account.auto_heal_agent_sa.email}"
}

resource "google_project_iam_member" "agent_trace_viewer" {
  project = var.project_id
  role    = "roles/cloudtrace.user"
  member  = "serviceAccount:${google_service_account.auto_heal_agent_sa.email}"
}

resource "google_project_iam_member" "agent_container_developer" {
  project = var.project_id
  role    = "roles/container.developer"
  member  = "serviceAccount:${google_service_account.auto_heal_agent_sa.email}"
}

resource "google_project_iam_member" "agent_vertex_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.auto_heal_agent_sa.email}"
}

# Workload Identity binding for Auto-Heal Agent
resource "google_service_account_iam_member" "workload_identity_binding" {
  service_account_id = google_service_account.auto_heal_agent_sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.agent_namespace}/${var.agent_k8s_service_account}]"
  
  depends_on = [var.cluster_name]  # Wait for cluster to be ready
}

# Service Account Key for external access (if needed)
resource "google_service_account_key" "auto_heal_agent_key" {
  count              = var.create_service_account_key ? 1 : 0
  service_account_id = google_service_account.auto_heal_agent_sa.name
  public_key_type    = "TYPE_X509_PEM_FILE"
}