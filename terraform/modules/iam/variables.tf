# Variables for IAM Module

variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "organization_id" {
  description = "The GCP organization ID (optional)"
  type        = string
  default     = ""
}

variable "grant_terraform_permissions" {
  description = "Whether to grant broad permissions to Terraform service account"
  type        = bool
  default     = false
}