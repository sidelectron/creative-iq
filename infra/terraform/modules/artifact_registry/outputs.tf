output "repository_url" {
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.main.repository_id}"
  description = "Base URL for docker push/pull."
}

output "repository_id" {
  value = google_artifact_registry_repository.main.repository_id
}
