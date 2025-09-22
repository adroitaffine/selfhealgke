# Variables for Networking Module

variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "network_name" {
  description = "Name of the VPC network"
  type        = string
  default     = "auto-heal-vpc"
}

variable "subnetwork_name" {
  description = "Name of the subnetwork"
  type        = string
  default     = "auto-heal-subnet"
}

variable "region" {
  description = "The region for the network resources"
  type        = string
  default     = "us-central1"
}

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