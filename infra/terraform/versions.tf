terraform {
  required_version = ">= 1.6.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      # vulnerability_scanning_config on Artifact Registry needs a recent 5.x / 6.x provider.
      version = ">= 5.44.0, < 7.0.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}
