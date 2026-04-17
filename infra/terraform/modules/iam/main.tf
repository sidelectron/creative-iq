data "google_project" "current" {
  project_id = var.project_id
}

locals {
  workload_pool = "${var.project_id}.svc.id.goog"
  ksas = {
    api            = "creativeiq-api"
    decomposition  = "creativeiq-decomposition"
    profile_engine = "creativeiq-profile-engine"
    chat           = "creativeiq-chat"
    airflow        = "creativeiq-airflow"
  }
}

resource "random_password" "jwt" {
  length  = 48
  special = false
}

resource "google_service_account" "api" {
  account_id   = "creativeiq-api"
  display_name = "CreativeIQ API"
}

resource "google_service_account" "decomposition" {
  account_id   = "creativeiq-decomposition"
  display_name = "CreativeIQ decomposition worker"
}

resource "google_service_account" "profile_engine" {
  account_id   = "creativeiq-profile-engine"
  display_name = "CreativeIQ profile engine"
}

resource "google_service_account" "chat" {
  account_id   = "creativeiq-chat"
  display_name = "CreativeIQ chat"
}

resource "google_service_account" "airflow" {
  account_id   = "creativeiq-airflow"
  display_name = "CreativeIQ Airflow workloads"
}

locals {
  service_accounts = {
    api            = google_service_account.api
    decomposition  = google_service_account.decomposition
    profile_engine = google_service_account.profile_engine
    chat           = google_service_account.chat
    airflow        = google_service_account.airflow
  }
}

resource "google_project_iam_member" "sql_client" {
  for_each = local.service_accounts

  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${each.value.email}"
}

resource "google_project_iam_member" "secret_accessor" {
  for_each = local.service_accounts

  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${each.value.email}"
}

resource "google_storage_bucket_iam_member" "api_read" {
  for_each = var.bucket_ids

  bucket = each.value
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.api.email}"
}

resource "google_storage_bucket_iam_member" "decomposition_rw" {
  for_each = var.bucket_ids

  bucket = each.value
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.decomposition.email}"
}

resource "google_storage_bucket_iam_member" "profile_rw" {
  for_each = var.bucket_ids

  bucket = each.value
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.profile_engine.email}"
}

resource "google_storage_bucket_iam_member" "airflow_rw" {
  for_each = var.bucket_ids

  bucket = each.value
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.airflow.email}"
}

resource "google_service_account_iam_member" "wi_api" {
  service_account_id = google_service_account.api.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${local.workload_pool}[${var.kubernetes_namespace}/${local.ksas.api}]"
}

resource "google_service_account_iam_member" "wi_decomposition" {
  service_account_id = google_service_account.decomposition.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${local.workload_pool}[${var.kubernetes_namespace}/${local.ksas.decomposition}]"
}

resource "google_service_account_iam_member" "wi_profile" {
  service_account_id = google_service_account.profile_engine.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${local.workload_pool}[${var.kubernetes_namespace}/${local.ksas.profile_engine}]"
}

resource "google_service_account_iam_member" "wi_chat" {
  service_account_id = google_service_account.chat.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${local.workload_pool}[${var.kubernetes_namespace}/${local.ksas.chat}]"
}

resource "google_service_account_iam_member" "wi_airflow" {
  service_account_id = google_service_account.airflow.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${local.workload_pool}[${var.kubernetes_namespace}/${local.ksas.airflow}]"
}

resource "google_secret_manager_secret" "database_url" {
  secret_id = "DATABASE_URL"

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  labels = {
    (var.rotation_reminder_label) = var.rotation_reminder_value
  }
}

resource "google_secret_manager_secret_version" "database_url" {
  secret      = google_secret_manager_secret.database_url.id
  secret_data = var.database_url
}

resource "google_secret_manager_secret" "redis_url" {
  secret_id = "REDIS_URL"

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  labels = {
    (var.rotation_reminder_label) = var.rotation_reminder_value
  }
}

resource "google_secret_manager_secret_version" "redis_url" {
  secret      = google_secret_manager_secret.redis_url.id
  secret_data = var.redis_url
}

resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "GEMINI_API_KEY"

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  labels = {
    (var.rotation_reminder_label) = var.rotation_reminder_value
  }
}

resource "google_secret_manager_secret_version" "gemini_api_key" {
  secret      = google_secret_manager_secret.gemini_api_key.id
  secret_data = var.gemini_api_key != "" ? var.gemini_api_key : "REPLACE_ME_SET_IN_SECRET_MANAGER"
}

resource "google_secret_manager_secret" "snowflake_password" {
  secret_id = "SNOWFLAKE_PASSWORD"

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  labels = {
    (var.rotation_reminder_label) = var.rotation_reminder_value
  }
}

resource "google_secret_manager_secret_version" "snowflake_password" {
  secret      = google_secret_manager_secret.snowflake_password.id
  secret_data = var.snowflake_password != "" ? var.snowflake_password : "REPLACE_ME_SET_IN_SECRET_MANAGER"
}

resource "google_secret_manager_secret" "jwt_secret_key" {
  secret_id = "JWT_SECRET_KEY"

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  labels = {
    (var.rotation_reminder_label) = var.rotation_reminder_value
  }
}

resource "google_secret_manager_secret_version" "jwt_secret_key" {
  secret      = google_secret_manager_secret.jwt_secret_key.id
  secret_data = random_password.jwt.result
}
