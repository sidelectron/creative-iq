variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "cluster_name" {
  type = string
}

variable "network_self_link" {
  type = string
}

variable "subnetwork_self_link" {
  type = string
}

variable "general_min_nodes" {
  type = number
}

variable "general_max_nodes" {
  type = number
}

variable "processing_min_nodes" {
  type = number
}

variable "processing_max_nodes" {
  type = number
}

variable "use_preemptible" {
  type = bool
}

variable "master_authorized_cidrs" {
  type = list(object({
    cidr_block   = string
    display_name = string
  }))
  default = []
}
