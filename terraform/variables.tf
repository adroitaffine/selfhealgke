# Variables for the root Terraform module

# Project and environment configuration
variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "environment" {
  description = "Environment name (development, staging, production)"
  type        = string
  default     = "production"
  
  validation {
    condition     = contains(["development", "staging", "production", "test"], var.environment)
    error_message = "Environment must be one of: development, staging, production, test."
  }
}

variable "region" {
  description = "The GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "organization_id" {
  description = "The GCP organization ID (optional)"
  type        = string
  default     = ""
}

# Terraform state management
variable "terraform_state_bucket" {
  description = "GCS bucket name for Terraform state"
  type        = string
}

# Networking configuration
variable "subnet_cidr" {
  description = "CIDR range for the main subnet"
  type        = string
  default     = "10.0.0.0/24"
}

variable "pods_cidr" {
  description = "CIDR range for pods secondary range"
  type        = string
  default     = "10.1.0.0/16"
}

variable "services_cidr" {
  description = "CIDR range for services secondary range"
  type        = string
  default     = "10.2.0.0/16"
}

variable "master_ipv4_cidr_block" {
  description = "CIDR block for the master nodes"
  type        = string
  default     = "172.16.0.0/28"
}

variable "authorized_networks" {
  description = "List of authorized networks for master access"
  type = list(object({
    cidr_block   = string
    display_name = string
  }))
  default = [
    {
      cidr_block   = "10.0.0.0/8"
      display_name = "Internal RFC1918"
    }
  ]
}

variable "ssh_source_ranges" {
  description = "Source IP ranges allowed for SSH access"
  type        = list(string)
  default     = ["35.235.240.0/20"] # Google Cloud IAP range
}

variable "webhook_source_ranges" {
  description = "Source IP ranges allowed for webhook access"
  type        = list(string)
  default     = ["0.0.0.0/0"] # Restrict this in production
}

# GKE cluster configuration
variable "maintenance_start_time" {
  description = "Start time for daily maintenance window"
  type        = string
  default     = "03:00"
}

# Node pool configuration
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

# Service account configuration
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

# IAM configuration
variable "grant_terraform_permissions" {
  description = "Whether to grant broad permissions to Terraform service account"
  type        = bool
  default     = false
}

# Monitoring configuration
variable "alert_email_addresses" {
  description = "List of email addresses for alert notifications"
  type        = list(string)
  default     = []
}

variable "force_destroy_bucket" {
  description = "Whether to force destroy the log bucket"
  type        = bool
  default     = false
}

variable "kms_key_name" {
  description = "KMS key name for bucket encryption (optional)"
  type        = string
  default     = null
}