# Development environment configuration

project_id  = "cogent-spirit-469200-q3"
environment = "development"
region      = "us-central1"

# Networking
subnet_cidr   = "10.10.0.0/24"
pods_cidr     = "10.11.0.0/16"
services_cidr = "10.12.0.0/16"

# GKE cluster configuration
min_node_count    = 1
max_node_count    = 3
machine_type      = "e2-standard-2"
disk_size_gb      = 30
preemptible_nodes = true

# Authorized networks (more permissive for development)
authorized_networks = [
  {
    cidr_block   = "10.0.0.0/8"
    display_name = "Internal RFC1918"
  },
  {
    cidr_block   = "172.16.0.0/12"
    display_name = "Internal RFC1918 172"
  }
]

# Monitoring
alert_email_addresses = [
  "dev-team@example.com"
]

# Development-specific settings
force_destroy_bucket         = true
create_service_account_key   = false
grant_terraform_permissions = true