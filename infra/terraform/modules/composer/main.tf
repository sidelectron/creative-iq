resource "google_composer_environment" "main" {
  name   = var.environment_name
  region = var.region

  config {
    environment_size = "ENVIRONMENT_SIZE_SMALL"

    software_config {
      image_version = var.image_version
    }

    node_config {
      network    = var.network
      subnetwork = var.subnetwork
    }
  }
}
