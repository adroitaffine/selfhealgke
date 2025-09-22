# Outputs for GKE Cluster Module

output "cluster_name" {
  description = "Name of the GKE cluster"
  value       = google_container_cluster.auto_heal_cluster.name
}

output "cluster_endpoint" {
  description = "Endpoint of the GKE cluster"
  value       = google_container_cluster.auto_heal_cluster.endpoint
  sensitive   = true
}

output "cluster_ca_certificate" {
  description = "CA certificate of the GKE cluster"
  value       = google_container_cluster.auto_heal_cluster.master_auth[0].cluster_ca_certificate
  sensitive   = true
}

output "cluster_location" {
  description = "Location of the GKE cluster"
  value       = google_container_cluster.auto_heal_cluster.location
}

output "node_pool_name" {
  description = "Name of the node pool"
  value       = google_container_node_pool.auto_heal_node_pool.name
}

output "gke_node_service_account_email" {
  description = "Email of the GKE node service account"
  value       = google_service_account.gke_node_sa.email
}

output "auto_heal_agent_service_account_email" {
  description = "Email of the auto-heal agent service account"
  value       = google_service_account.auto_heal_agent_sa.email
}

output "auto_heal_agent_service_account_key" {
  description = "Private key of the auto-heal agent service account"
  value       = var.create_service_account_key ? google_service_account_key.auto_heal_agent_key[0].private_key : null
  sensitive   = true
}

output "cluster_master_version" {
  description = "Master version of the GKE cluster"
  value       = google_container_cluster.auto_heal_cluster.master_version
}

output "cluster_node_version" {
  description = "Node version of the GKE cluster"
  value       = google_container_node_pool.auto_heal_node_pool.version
}