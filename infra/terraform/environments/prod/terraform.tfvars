# Project number: 1098684191956
project_id  = "creativeiq-493423"
region      = "us-east1"
zone        = "us-east1-b"
environment = "prod"

cluster_name         = "creativeiq-gke-prod"
bucket_name_prefix   = "creativeiq"
db_name              = "creative_intelligence"
db_user              = "ci_user"

redis_memory_size_gb = 5
redis_tier           = "STANDARD_HA"

gke_general_min_nodes    = 2
gke_general_max_nodes    = 6
gke_processing_min_nodes = 0
gke_processing_max_nodes = 5
gke_use_preemptible      = false

sql_tier                  = "db-custom-2-4096"
sql_disk_size_gb          = 50
sql_high_availability     = true
sql_backup_retention_days = 30

master_authorized_cidrs = []

frontend_cors_origin = "https://REPLACE_WITH_APP_HOSTNAME"
domain               = "REPLACE_WITH_APP_HOSTNAME"

enable_composer             = true
composer_environment_name = "creativeiq-composer-prod"
composer_image_version    = "composer-3-airflow-2.10.2-build.5"

terraform_deployer_email = ""
