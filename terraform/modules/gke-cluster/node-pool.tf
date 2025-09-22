# Node Pool Configuration with Autoscaling

resource "google_container_node_pool" "auto_heal_node_pool" {
  name       = var.node_pool_name
  location   = var.region
  cluster    = google_container_cluster.auto_heal_cluster.name
  project    = var.project_id

  # Autoscaling configuration
  autoscaling {
    min_node_count = var.min_node_count
    max_node_count = var.max_node_count
  }

  # Node configuration
  node_config {
    preemptible  = var.preemptible_nodes
    machine_type = var.machine_type
    disk_size_gb = var.disk_size_gb
    disk_type    = var.disk_type

    # Service account
    service_account = google_service_account.gke_node_sa.email

    # OAuth scopes
    oauth_scopes = [
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring",
      "https://www.googleapis.com/auth/devstorage.read_only",
      "https://www.googleapis.com/auth/servicecontrol",
      "https://www.googleapis.com/auth/service.management.readonly",
      "https://www.googleapis.com/auth/trace.append",
    ]

    # Node labels
    labels = merge(var.node_labels, {
      "cluster" = var.cluster_name
      "pool"    = var.node_pool_name
    })

    # Node taints
    dynamic "taint" {
      for_each = var.node_taints
      content {
        key    = taint.value.key
        value  = taint.value.value
        effect = taint.value.effect
      }
    }

    # Shielded instance configuration
    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }

    # Workload metadata configuration
    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    # Resource labels
    resource_labels = var.node_labels
  }

  # Node management
  management {
    auto_repair  = true
    auto_upgrade = true
  }

  # Upgrade settings
  upgrade_settings {
    max_surge       = var.max_surge
    max_unavailable = var.max_unavailable
  }

  # Lifecycle management
  lifecycle {
    ignore_changes = [
      initial_node_count,
    ]
  }
}