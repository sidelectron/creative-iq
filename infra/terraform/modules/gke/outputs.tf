output "cluster_name" {
  value = google_container_cluster.main.name
}

output "cluster_location" {
  value = google_container_cluster.main.location
}

output "cluster_endpoint" {
  value     = google_container_cluster.main.endpoint
  sensitive = true
}
