variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "environment" {
  type = string
}

variable "kubernetes_namespace" {
  type    = string
  default = "creativeiq"
}

variable "database_url" {
  type        = string
  description = "Full asyncpg-style DATABASE_URL (sensitive)."
  sensitive   = true
}

variable "redis_url" {
  type        = string
  sensitive   = true
}

variable "bucket_ids" {
  type        = map(string)
  description = "Logical to physical bucket names for IAM bindings."
}

variable "gemini_api_key" {
  type        = string
  sensitive   = true
  default     = ""
  description = "If empty, secret version is set to a placeholder string."
}

variable "snowflake_password" {
  type        = string
  sensitive   = true
  default     = ""
}

variable "rotation_reminder_label" {
  type    = string
  default = "rotation_policy"
}

variable "rotation_reminder_value" {
  type    = string
  default = "review_90d"
}
