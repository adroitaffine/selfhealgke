# Networking Module for GKE Auto-Heal Agent
# Creates VPC network and subnets for VPC-native GKE cluster

# VPC Network
resource "google_compute_network" "auto_heal_vpc" {
  name                    = var.network_name
  project                 = var.project_id
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
  description             = "VPC network for GKE Auto-Heal Agent"
}

# Subnet for GKE cluster
resource "google_compute_subnetwork" "auto_heal_subnet" {
  name          = var.subnetwork_name
  project       = var.project_id
  ip_cidr_range = var.subnet_cidr
  region        = var.region
  network       = google_compute_network.auto_heal_vpc.id
  description   = "Subnet for GKE Auto-Heal Agent cluster"

  # Secondary ranges for pods and services
  secondary_ip_range {
    range_name    = var.pods_secondary_range_name
    ip_cidr_range = var.pods_cidr
  }

  secondary_ip_range {
    range_name    = var.services_secondary_range_name
    ip_cidr_range = var.services_cidr
  }

  # Private Google Access
  private_ip_google_access = true

  # Flow logs
  log_config {
    aggregation_interval = "INTERVAL_10_MIN"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

# Cloud Router for NAT
resource "google_compute_router" "auto_heal_router" {
  name    = "${var.network_name}-router"
  project = var.project_id
  region  = var.region
  network = google_compute_network.auto_heal_vpc.id

  bgp {
    asn = 64514
  }
}

# Cloud NAT for outbound internet access
resource "google_compute_router_nat" "auto_heal_nat" {
  name                               = "${var.network_name}-nat"
  project                            = var.project_id
  router                             = google_compute_router.auto_heal_router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# Firewall rules
resource "google_compute_firewall" "allow_internal" {
  name    = "${var.network_name}-allow-internal"
  project = var.project_id
  network = google_compute_network.auto_heal_vpc.name

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = [
    var.subnet_cidr,
    var.pods_cidr,
    var.services_cidr,
  ]

  description = "Allow internal communication within VPC"
}

resource "google_compute_firewall" "allow_ssh" {
  name    = "${var.network_name}-allow-ssh"
  project = var.project_id
  network = google_compute_network.auto_heal_vpc.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = var.ssh_source_ranges
  target_tags   = ["ssh-allowed"]

  description = "Allow SSH access from authorized networks"
}

resource "google_compute_firewall" "allow_webhook" {
  name    = "${var.network_name}-allow-webhook"
  project = var.project_id
  network = google_compute_network.auto_heal_vpc.name

  allow {
    protocol = "tcp"
    ports    = ["8080", "443"]
  }

  source_ranges = var.webhook_source_ranges
  target_tags   = ["webhook-server"]

  description = "Allow webhook traffic to auto-heal agent"
}