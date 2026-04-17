output "network_id" {
  value = google_compute_network.main.id
}

output "network_self_link" {
  value = google_compute_network.main.self_link
}

output "subnet_gke_self_link" {
  value = google_compute_subnetwork.gke.self_link
}

output "subnet_gke_name" {
  value = google_compute_subnetwork.gke.name
}

output "subnet_data_self_link" {
  value = google_compute_subnetwork.data.self_link
}

output "subnet_data_name" {
  value = google_compute_subnetwork.data.name
}
