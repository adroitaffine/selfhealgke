# Variables for GKE Cluster Module

variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "cluster_name" {
  description = "Name of the GKE cluster"
  type        = string
  default     = "gke-auto-heal-cluster"
}

variable "region" {
  description = "The region for the GKE cluster"
  type        = string
  default     = "us-central1"
}

variable "network_name" {
  description = "Name of the VPC network"
  type        = string
}

variable "subnetwork_name" {
  description = "Name of the subnetwork"
  type        = string
}

variable "master_ipv4_cidr_block" {
  description = "CIDR block for the master nodes"
  type        = string
  default     = "172.16.0.0/28"
}

variable "pods_secondary_range_name" {
  description = "Name of the secondary range for pods"
  type        = string
  default     = "pods"
}

variable "services_secondary_range_name" {
  description = "Name of the secondary range for services"
  type        = string
  default     = "services"
}

variable "authorized_networks" {
  description = "List of authorized networks for master access"
  type = list(object({
    cidr_block   = string
    display_name = string
  }))
  default = []
}

variable "cluster_labels" {
  description = "Labels to apply to the cluster"
  type        = map(string)
  default = {
    environment = "production"
    managed-by  = "terraform"
    purpose     = "auto-heal-agent"
  }
}

variable "maintenance_start_time" {
  description = "Start time for daily maintenance window"
  type        = string
  default     = "03:00"
}

# Node Pool Variables
variable "node_pool_name" {
  description = "Name of the node pool"
  type        = string
  default     = "auto-heal-node-pool"
}

variable "min_node_count" {
  description = "Minimum number of nodes in the pool"
  type        = number
  default     = 1
}

variable "max_node_count" {
  description = "Maximum number of nodes in the pool"
  type        = number
  default     = 5
}

variable "machine_type" {
  description = "Machine type for nodes"
  type        = string
  default     = "e2-standard-2"
}

variable "disk_size_gb" {
  description = "Disk size in GB for nodes"
  type        = number
  default     = 50
}

variable "disk_type" {
  description = "Disk type for nodes"
  type        = string
  default     = "pd-standard"
}

variable "preemptible_nodes" {
  description = "Whether to use preemptible nodes"
  type        = bool
  default     = false
}

variable "node_labels" {
  description = "Labels to apply to nodes"
  type        = map(string)
  default = {
    environment = "production"
    managed-by  = "terraform"
  }
}

variable "node_taints" {
  description = "Taints to apply to nodes"
  type = list(object({
    key    = string
    value  = string
    effect = string
  }))
  default = []
}

variable "max_surge" {
  description = "Maximum number of nodes that can be created during upgrade"
  type        = number
  default     = 1
}

variable "max_unavailable" {
  description = "Maximum number of nodes that can be unavailable during upgrade"
  type        = number
  default     = 0
}

# Service Account Variables
variable "agent_namespace" {
  description = "Kubernetes namespace for the auto-heal agent"
  type        = string
  default     = "auto-heal"
}

variable "agent_k8s_service_account" {
  description = "Kubernetes service account name for the auto-heal agent"
  type        = string
  default     = "auto-heal-agent"
}

variable "create_service_account_key" {
  description = "Whether to create a service account key"
  type        = bool
  default     = false
}