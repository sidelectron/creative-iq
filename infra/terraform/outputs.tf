output "gke_cluster_name" {
  value       = module.gke.cluster_name
  description = "GKE cluster name."
}

output "gke_cluster_location" {
  value       = module.gke.cluster_location
  description = "GKE cluster region."
}

output "artifact_registry_repository" {
  value       = module.artifact_registry.repository_url
  description = "Docker repository URL for images."
}

output "github_cd_service_account_email" {
  value       = var.enable_github_cd_service_account ? google_service_account.github_cd[0].email : null
  description = "Email of the Terraform-managed GitHub CD SA when enable_github_cd_service_account is true; create a JSON key for it and set GitHub secret GCP_SA_KEY."
}

output "gcs_bucket_names" {
  value       = module.gcs.bucket_names
  description = "Map of logical bucket keys to GCS names."
}

output "cloud_sql_connection_name" {
  value       = module.cloud_sql.connection_name
  description = "Cloud SQL instance connection name for Cloud SQL Proxy / connectors."
}

output "memorystore_host" {
  value       = module.memorystore.host
  description = "Memorystore Redis host (private IP)."
}

output "kubernetes_namespace" {
  value       = "creativeiq"
  description = "Target namespace for workloads (matches k8s manifests)."
}

output "composer_environment_id" {
  value       = length(module.composer) > 0 ? module.composer[0].environment_id : null
  description = "Composer environment ID if enabled."
}

output "composer_dags_bucket" {
  value       = length(module.composer) > 0 ? module.composer[0].dag_gcs_prefix : null
  description = "GCS URI prefix for DAG sync if Composer enabled."
}
