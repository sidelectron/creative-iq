variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "network_name" {
  type        = string
  description = "VPC name (spec: creativeiq-vpc)."
  default     = "creativeiq-vpc"
}

variable "gke_subnet_cidr" {
  type    = string
  default = "10.0.0.0/20"
}

variable "gke_pods_secondary_cidr" {
  type    = string
  default = "10.4.0.0/14"
}

variable "gke_services_secondary_cidr" {
  type    = string
  default = "10.8.0.0/20"
}

variable "data_subnet_cidr" {
  type    = string
  default = "10.0.16.0/24"
}

variable "proxy_subnet_cidr" {
  type    = string
  default = "10.0.17.0/26"
}

variable "psa_prefix_length" {
  type    = number
  default = 16
}
