output "service_account_emails" {
  value = {
    api            = google_service_account.api.email
    decomposition  = google_service_account.decomposition.email
    profile_engine = google_service_account.profile_engine.email
    chat           = google_service_account.chat.email
    airflow        = google_service_account.airflow.email
  }
}

output "workload_identity_annotations" {
  value = {
    api            = google_service_account.api.email
    decomposition  = google_service_account.decomposition.email
    profile_engine = google_service_account.profile_engine.email
    chat           = google_service_account.chat.email
    airflow        = google_service_account.airflow.email
  }
  description = "Use as iam.gke.io/gcp-service-account annotation value per KSA."
}
