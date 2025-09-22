# Staging environment configuration

project_id  = "cogent-spirit-469200-q3"
environment = "staging"
region      = "us-central1"

# Networking
subnet_cidr   = "10.20.0.0/24"
pods_cidr     = "10.21.0.0/16"
services_cidr = "10.22.0.0/16"

# GKE cluster configuration
min_node_count    = 2
max_node_count    = 10
machine_type      = "e2-standard-4"
disk_size_gb      = 50
preemptible_nodes = false

# Authorized networks (restricted)
authorized_networks = [
  {
    cidr_block   = "10.0.0.0/8"
    display_name = "Internal RFC1918"
  }
]

# Monitoring
alert_email_addresses = [
  "staging-alerts@example.com",
  "sre-team@example.com"
]

# Staging-specific settings
force_destroy_bucket         = false
create_service_account_key   = false
grant_terraform_permissions = false