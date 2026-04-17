variable "region" {
  type = string
}

variable "environment" {
  type = string
}

variable "network_id" {
  type = string
}

variable "memory_size_gb" {
  type = number
}

variable "tier" {
  type = string
}

variable "redis_version" {
  type    = string
  default = "REDIS_7_0"
}
