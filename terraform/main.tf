# Main Terraform configuration for GKE Auto-Heal Agent
# This is the root module that orchestrates all infrastructure components

terraform {
  required_version = ">= 1.5"
  
  # Backend configuration for state management
  backend "gcs" {
    bucket  = var.terraform_state_bucket
    prefix  = "terraform/state"
    # encryption_key is set via environment variable GOOGLE_ENCRYPTION_KEY
  }
}

# Configure the Google Cloud Provider
provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# Local values for common configurations
locals {
  common_labels = {
    project     = "gke-auto-heal-agent"
    managed-by  = "terraform"
    environment = var.environment
    purpose     = "auto-heal-agent"
  }
  
  cluster_name = "${var.environment}-auto-heal"
}

# Networking module
module "networking" {
  source = "./modules/networking"
  
  project_id                      = var.project_id
  network_name                    = "${local.cluster_name}-vpc"
  subnetwork_name                 = "${local.cluster_name}-subnet"
  region                          = var.region
  subnet_cidr                     = var.subnet_cidr
  pods_cidr                       = var.pods_cidr
  services_cidr                   = var.services_cidr
  pods_secondary_range_name       = "pods"
  services_secondary_range_name   = "services"
  ssh_source_ranges               = var.ssh_source_ranges
  webhook_source_ranges           = var.webhook_source_ranges
}

# IAM module
module "iam" {
  source = "./modules/iam"
  
  project_id                    = var.project_id
  organization_id               = var.organization_id
  grant_terraform_permissions  = var.grant_terraform_permissions
}

# GKE cluster module
module "gke_cluster" {
  source = "./modules/gke-cluster"
  
  project_id                        = var.project_id
  cluster_name                      = local.cluster_name
  region                            = var.region
  network_name                      = module.networking.network_name
  subnetwork_name                   = module.networking.subnetwork_name
  master_ipv4_cidr_block           = var.master_ipv4_cidr_block
  pods_secondary_range_name        = module.networking.pods_secondary_range_name
  services_secondary_range_name    = module.networking.services_secondary_range_name
  authorized_networks              = var.authorized_networks
  cluster_labels                   = local.common_labels
  maintenance_start_time           = var.maintenance_start_time
  
  # Node pool configuration
  node_pool_name                   = "${local.cluster_name}-nodes"
  min_node_count                   = var.min_node_count
  max_node_count                   = var.max_node_count
  machine_type                     = var.machine_type
  disk_size_gb                     = var.disk_size_gb
  disk_type                        = var.disk_type
  preemptible_nodes                = var.preemptible_nodes
  node_labels                      = local.common_labels
  node_taints                      = var.node_taints
  max_surge                        = var.max_surge
  max_unavailable                  = var.max_unavailable
  
  # Service account configuration
  agent_namespace                  = var.agent_namespace
  agent_k8s_service_account        = var.agent_k8s_service_account
  create_service_account_key       = var.create_service_account_key
}

# Monitoring module
module "monitoring" {
  source = "./modules/monitoring"
  
  project_id              = var.project_id
  region                  = var.region
  cluster_name            = module.gke_cluster.cluster_name
  agent_namespace         = var.agent_namespace
  alert_email_addresses   = var.alert_email_addresses
  force_destroy_bucket    = var.force_destroy_bucket
  kms_key_name           = var.kms_key_name
}