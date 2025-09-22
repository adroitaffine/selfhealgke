# Outputs for Networking Module

output "network_name" {
  description = "Name of the VPC network"
  value       = google_compute_network.auto_heal_vpc.name
}

output "network_id" {
  description = "ID of the VPC network"
  value       = google_compute_network.auto_heal_vpc.id
}

output "subnetwork_name" {
  description = "Name of the subnetwork"
  value       = google_compute_subnetwork.auto_heal_subnet.name
}

output "subnetwork_id" {
  description = "ID of the subnetwork"
  value       = google_compute_subnetwork.auto_heal_subnet.id
}

output "subnet_cidr" {
  description = "CIDR range of the main subnet"
  value       = google_compute_subnetwork.auto_heal_subnet.ip_cidr_range
}

output "pods_secondary_range_name" {
  description = "Name of the pods secondary range"
  value       = var.pods_secondary_range_name
}

output "services_secondary_range_name" {
  description = "Name of the services secondary range"
  value       = var.services_secondary_range_name
}

output "router_name" {
  description = "Name of the Cloud Router"
  value       = google_compute_router.auto_heal_router.name
}

output "nat_name" {
  description = "Name of the Cloud NAT"
  value       = google_compute_router_nat.auto_heal_nat.name
}