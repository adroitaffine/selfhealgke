# Variables for Monitoring Module

variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "region" {
  description = "The region for monitoring resources"
  type        = string
  default     = "us-central1"
}

variable "cluster_name" {
  description = "Name of the GKE cluster"
  type        = string
}

variable "agent_namespace" {
  description = "Kubernetes namespace for the auto-heal agent"
  type        = string
  default     = "auto-heal"
}

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