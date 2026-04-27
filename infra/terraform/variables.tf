variable "project_id" {
  type        = string
  description = "GCP project ID."
}

variable "region" {
  type        = string
  description = "Primary GCP region (e.g. us-east1)."
}

variable "zone" {
  type        = string
  description = "Primary zone within region (e.g. us-east1-b)."
}

variable "environment" {
  type        = string
  description = "Environment name: dev or prod."
}

variable "cluster_name" {
  type        = string
  description = "GKE cluster name."
}

variable "bucket_name_prefix" {
  type        = string
  description = "Prefix for GCS buckets (spec: creativeiq-{env}-*; align STORAGE_BUCKET_* in apps)."
  default     = "creativeiq"
}

variable "db_name" {
  type        = string
  description = "Logical PostgreSQL database name. Default matches docker-compose + Alembic (creative_intelligence); override to creativeiq if you align migrations to the Phase 9 spec name."
  default     = "creative_intelligence"
}

variable "db_user" {
  type        = string
  description = "Application database user."
  default     = "ci_user"
}

variable "redis_memory_size_gb" {
  type        = number
  description = "Memorystore memory size in GB."
}

variable "redis_tier" {
  type        = string
  description = "BASIC or STANDARD_HA."
}

variable "gke_general_min_nodes" {
  type        = number
  description = "General node pool minimum nodes."
}

variable "gke_general_max_nodes" {
  type        = number
  description = "General node pool maximum nodes."
}

variable "gke_processing_min_nodes" {
  type        = number
  description = "Processing node pool minimum nodes (0 for scale-to-zero when supported)."
}

variable "gke_processing_max_nodes" {
  type        = number
  description = "Processing node pool maximum nodes."
}

variable "gke_use_preemptible" {
  type        = bool
  description = "Use preemptible/spot nodes (dev cost savings)."
}

variable "gke_node_locations" {
  type        = list(string)
  description = "Optional zones for regional GKE nodes (default pool + custom pools). Use a single zone in dev to avoid GCE_STOCKOUT. Empty = all zones in the region."
  default     = []
}

variable "sql_tier" {
  type        = string
  description = "Cloud SQL machine tier."
}

variable "sql_disk_size_gb" {
  type        = number
  description = "Cloud SQL disk size GB."
}

variable "sql_high_availability" {
  type        = bool
  description = "Enable regional HA for Cloud SQL."
}

variable "sql_backup_retention_days" {
  type        = number
  description = "Automated backup retention days."
}

variable "master_authorized_cidrs" {
  type = list(object({
    cidr_block   = string
    display_name = string
  }))
  description = "Authorized networks for GKE control plane (dev home IP, bastion, etc.)."
  default     = []
}

variable "frontend_cors_origin" {
  type        = string
  description = "Frontend origin for GCS CORS (e.g. https://app.example.com)."
  default     = "https://localhost:3000"
}

variable "domain" {
  type        = string
  description = "Optional DNS hostname for managed certificate (empty to skip managed cert)."
  default     = ""
}

variable "enable_composer" {
  type        = bool
  description = "Provision Cloud Composer 2 (material cost; disable in sandbox)."
  default     = true
}

variable "composer_environment_name" {
  type        = string
  description = "Composer environment resource name."
  default     = "creativeiq-composer"
}

variable "terraform_deployer_email" {
  type        = string
  description = "Optional legacy single SA email (no prefix) granted roles/artifactregistry.writer on the image repo. Prefer artifact_registry_writer_emails; values are merged."
  default     = ""
}

variable "artifact_registry_writer_emails" {
  type        = list(string)
  description = "Service account emails (no serviceAccount: prefix) that can push Docker images. Merged with terraform_deployer_email and (when enabled) the Terraform-managed GitHub CD SA; must still match GitHub secret GCP_SA_KEY client_email unless you rotate the secret to the managed SA."
  default     = []
}

variable "enable_github_cd_service_account" {
  type        = bool
  description = "When true, creates creativeiq-gha-{environment}@… with roles/container.developer and grants it roles/artifactregistry.writer on the image repo. Create a JSON key for that SA and set GitHub secret GCP_SA_KEY."
  default     = false
}

variable "bootstrap_gemini_api_key" {
  type        = string
  description = "Optional: if set, written to Secret Manager GEMINI_API_KEY version (otherwise placeholder)."
  default     = ""
  sensitive   = true
}

variable "bootstrap_snowflake_password" {
  type        = string
  description = "Optional: if set, written to Secret Manager SNOWFLAKE_PASSWORD version (otherwise placeholder)."
  default     = ""
  sensitive   = true
}

variable "composer_image_version" {
  type        = string
  description = "Composer environment image version; update when deprecated by Google."
  default     = "composer-3-airflow-2.10.2-build.5"
}
