variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "network" {
  type        = string
  description = "VPC self link."
}

variable "subnetwork" {
  type        = string
  description = "Data subnet self link for Composer nodes."
}

variable "environment_name" {
  type = string
}

variable "image_version" {
  type        = string
  description = "Composer image version string for the region (update when Google deprecates)."
}
