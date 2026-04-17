resource "google_redis_instance" "main" {
  name           = "creativeiq-redis-${var.environment}"
  tier           = var.tier
  memory_size_gb = var.memory_size_gb
  region         = var.region
  redis_version  = var.redis_version

  connect_mode         = "PRIVATE_SERVICE_ACCESS"
  authorized_network   = var.network_id

  display_name = "CreativeIQ Redis ${var.environment}"
}
