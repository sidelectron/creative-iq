locals {
  database_url = format(
    "postgresql+asyncpg://%s:%s@%s:5432/%s",
    var.db_user,
    module.cloud_sql.db_password,
    module.cloud_sql.private_ip_address,
    var.db_name
  )
  redis_url = format("redis://%s:%s/0", module.memorystore.host, module.memorystore.port)

  # SAs that can docker push to Artifact Registry (GitHub CD uses secrets.GCP_SA_KEY).
  artifact_registry_writer_sa_emails = distinct(compact(concat(
    var.terraform_deployer_email != "" ? [replace(var.terraform_deployer_email, "serviceAccount:", "")] : [],
    [for e in var.artifact_registry_writer_emails : replace(e, "serviceAccount:", "")],
    var.enable_github_cd_service_account ? [google_service_account.github_cd[0].email] : [],
  )))
}

resource "google_service_account" "github_cd" {
  count = var.enable_github_cd_service_account ? 1 : 0

  project      = var.project_id
  account_id   = "creativeiq-gha-${var.environment}"
  display_name = "GitHub Actions CD (${var.environment})"
  description  = "Pushes images to Artifact Registry and deploys to GKE via GitHub Actions; use a key for this SA in GCP_SA_KEY."
}

resource "google_project_iam_member" "github_cd_container_developer" {
  count = var.enable_github_cd_service_account ? 1 : 0

  project = var.project_id
  role    = "roles/container.developer"
  member  = "serviceAccount:${google_service_account.github_cd[0].email}"
}

module "vpc" {
  source = "./modules/vpc"

  project_id = var.project_id
  region     = var.region
}

module "gcs" {
  source = "./modules/gcs"

  project_id           = var.project_id
  region               = var.region
  environment          = var.environment
  bucket_name_prefix   = var.bucket_name_prefix
  frontend_cors_origin = var.frontend_cors_origin
}

module "artifact_registry" {
  source = "./modules/artifact_registry"

  project_id                    = var.project_id
  region                        = var.region
  writer_service_account_emails = local.artifact_registry_writer_sa_emails
}

module "cloud_sql" {
  source = "./modules/cloud_sql"

  region                = var.region
  environment           = var.environment
  network_self_link     = module.vpc.network_self_link
  tier                  = var.sql_tier
  disk_size_gb          = var.sql_disk_size_gb
  high_availability     = var.sql_high_availability
  backup_retention_days = var.sql_backup_retention_days
  db_name               = var.db_name
  db_user               = var.db_user

  depends_on = [module.vpc]
}

module "memorystore" {
  source = "./modules/memorystore"

  region         = var.region
  environment    = var.environment
  network_id     = module.vpc.network_id
  memory_size_gb = var.redis_memory_size_gb
  tier           = var.redis_tier

  depends_on = [module.vpc]
}

module "gke" {
  source = "./modules/gke"

  environment             = var.environment
  project_id              = var.project_id
  region                  = var.region
  cluster_name            = var.cluster_name
  network_self_link       = module.vpc.network_self_link
  subnetwork_self_link    = module.vpc.subnet_gke_self_link
  general_min_nodes       = var.gke_general_min_nodes
  general_max_nodes       = var.gke_general_max_nodes
  processing_min_nodes    = var.gke_processing_min_nodes
  processing_max_nodes    = var.gke_processing_max_nodes
  use_preemptible         = var.gke_use_preemptible
  node_locations          = var.gke_node_locations
  master_authorized_cidrs = var.master_authorized_cidrs

  depends_on = [module.vpc]
}

module "iam" {
  source = "./modules/iam"

  project_id         = var.project_id
  region             = var.region
  environment        = var.environment
  database_url       = local.database_url
  redis_url          = local.redis_url
  bucket_ids         = module.gcs.bucket_names
  gemini_api_key     = var.bootstrap_gemini_api_key
  snowflake_password = var.bootstrap_snowflake_password

  depends_on = [
    module.cloud_sql,
    module.memorystore,
    module.gcs,
    module.gke,
  ]
}

module "composer" {
  count  = var.enable_composer ? 1 : 0
  source = "./modules/composer"

  project_id       = var.project_id
  region           = var.region
  network          = module.vpc.network_self_link
  subnetwork       = module.vpc.subnet_data_self_link
  environment_name = var.composer_environment_name
  image_version    = var.composer_image_version

  depends_on = [module.vpc]
}
