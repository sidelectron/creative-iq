variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "repository_id" {
  type    = string
  default = "creativeiq-images"
}

variable "terraform_deployer_email" {
  type        = string
  description = "Optional deployer SA email for push access."
  default     = ""
}
