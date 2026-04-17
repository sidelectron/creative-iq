resource "google_artifact_registry_repository" "main" {
  location      = var.region
  repository_id = var.repository_id
  description   = "CreativeIQ container images"
  format        = "DOCKER"

  # Phase 9: Artifact Analysis. Provider allows INHERITED | DISABLED; INHERITED follows org/project defaults (scanning on by default for Docker repos).
  vulnerability_scanning_config {
    enablement_config = "INHERITED"
  }
}

data "google_project" "current" {
  project_id = var.project_id
}

resource "google_artifact_registry_repository_iam_member" "gke_nodes_reader" {
  project    = google_artifact_registry_repository.main.project
  location   = google_artifact_registry_repository.main.location
  repository = google_artifact_registry_repository.main.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${data.google_project.current.number}-compute@developer.gserviceaccount.com"
}

resource "google_artifact_registry_repository_iam_member" "deployer_writer" {
  count = var.terraform_deployer_email != "" ? 1 : 0

  project    = google_artifact_registry_repository.main.project
  location   = google_artifact_registry_repository.main.location
  repository = google_artifact_registry_repository.main.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${var.terraform_deployer_email}"
}
