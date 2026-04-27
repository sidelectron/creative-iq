# Console: Project number 1098684191956 — Terraform uses project_id string below.
project_id  = "creativeiq-493423"
region      = "us-east1"
zone        = "us-east1-b"
environment = "dev"

cluster_name       = "creativeiq-gke-dev"
bucket_name_prefix = "creativeiq"
db_name            = "creative_intelligence"
db_user            = "ci_user"

redis_memory_size_gb = 1
redis_tier           = "BASIC"

gke_general_min_nodes    = 1
gke_general_max_nodes    = 3
gke_processing_min_nodes = 0
gke_processing_max_nodes = 3
gke_use_preemptible      = true
# Regional cluster default pool can land in zones with stockout; pin to one zone for dev.
gke_node_locations = ["us-east1-d"]

sql_tier                  = "db-f1-micro"
sql_disk_size_gb          = 10
sql_high_availability     = false
sql_backup_retention_days = 7

master_authorized_cidrs = [
  # Replace with your public IP /32 for kubectl to a private-nodes cluster (public control plane endpoint).
  # { cidr_block = "203.0.113.10/32", display_name = "home" },
]

frontend_cors_origin = "http://localhost:3000"
domain               = ""

enable_composer           = false
composer_environment_name = "creativeiq-composer-dev"
composer_image_version    = "composer-3-airflow-2.10.2-build.5"

terraform_deployer_email = ""

# Creates creativeiq-gha-dev@… with Artifact Registry writer + GKE developer; then create a
# JSON key for that SA (IAM → SA → Keys) and set GitHub secret GCP_SA_KEY to fix docker push.
enable_github_cd_service_account = true

# Optional extra pushers (emails without serviceAccount: prefix). Not needed if using the managed SA above.
artifact_registry_writer_emails = []
