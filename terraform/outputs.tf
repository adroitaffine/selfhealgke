# Outputs for the root Terraform module

# Networking outputs
output "network_name" {
  description = "Name of the VPC network"
  value       = module.networking.network_name
}

output "subnetwork_name" {
  description = "Name of the subnetwork"
  value       = module.networking.subnetwork_name
}

# GKE cluster outputs
output "cluster_name" {
  description = "Name of the GKE cluster"
  value       = module.gke_cluster.cluster_name
}

output "cluster_endpoint" {
  description = "Endpoint of the GKE cluster"
  value       = module.gke_cluster.cluster_endpoint
  sensitive   = true
}

output "cluster_ca_certificate" {
  description = "CA certificate of the GKE cluster"
  value       = module.gke_cluster.cluster_ca_certificate
  sensitive   = true
}

output "cluster_location" {
  description = "Location of the GKE cluster"
  value       = module.gke_cluster.cluster_location
}

# Service account outputs
output "gke_node_service_account_email" {
  description = "Email of the GKE node service account"
  value       = module.gke_cluster.gke_node_service_account_email
}

output "auto_heal_agent_service_account_email" {
  description = "Email of the auto-heal agent service account"
  value       = module.gke_cluster.auto_heal_agent_service_account_email
}

output "auto_heal_agent_service_account_key" {
  description = "Private key of the auto-heal agent service account"
  value       = module.gke_cluster.auto_heal_agent_service_account_key
  sensitive   = true
}

output "terraform_service_account_email" {
  description = "Email of the Terraform service account"
  value       = module.iam.terraform_service_account_email
}

output "monitoring_service_account_email" {
  description = "Email of the monitoring service account"
  value       = module.iam.monitoring_service_account_email
}

# Monitoring outputs
output "log_bucket_name" {
  description = "Name of the log storage bucket"
  value       = module.monitoring.log_bucket_name
}

output "dashboard_id" {
  description = "ID of the monitoring dashboard"
  value       = module.monitoring.dashboard_id
}

# Connection information for kubectl
output "kubectl_config_command" {
  description = "Command to configure kubectl"
  value       = "gcloud container clusters get-credentials ${module.gke_cluster.cluster_name} --region ${var.region} --project ${var.project_id}"
}