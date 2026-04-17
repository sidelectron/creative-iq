variable "region" {
  type = string
}

variable "environment" {
  type = string
}

variable "network_self_link" {
  type = string
}

variable "tier" {
  type = string
}

variable "disk_size_gb" {
  type = number
}

variable "high_availability" {
  type = bool
}

variable "backup_retention_days" {
  type = number
}

variable "db_name" {
  type = string
}

variable "db_user" {
  type = string
}

variable "instance_name" {
  type    = string
  default = "creativeiq-postgres"
}
