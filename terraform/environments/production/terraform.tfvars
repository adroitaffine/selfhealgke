# Production environment configuration

project_id  = "cogent-spirit-469200-q3"
environment = "production"
region      = "us-central1"

# Networking
subnet_cidr   = "10.30.0.0/24"
pods_cidr     = "10.31.0.0/16"
services_cidr = "10.32.0.0/16"

# GKE cluster configuration
min_node_count    = 3
max_node_count    = 50
machine_type      = "e2-standard-4"
disk_size_gb      = 100
disk_type         = "pd-ssd"
preemptible_nodes = false

# Node pool upgrade settings (more conservative)
max_surge       = 1
max_unavailable = 0

# Authorized networks (most restrictive)
authorized_networks = [
  {
    cidr_block   = "10.30.0.0/16"
    display_name = "Production VPC"
  }
]

# Maintenance window (early morning)
maintenance_start_time = "02:00"

# Monitoring
alert_email_addresses = [
  "production-alerts@example.com",
  "sre-team@example.com",
  "on-call@example.com"
]

# Production-specific settings
force_destroy_bucket         = false
create_service_account_key   = false
grant_terraform_permissions = false

# Security settings
ssh_source_ranges = [
  "35.235.240.0/20"  # Google Cloud IAP only
]

webhook_source_ranges = [
  "10.30.0.0/16"  # Only from production VPC
]