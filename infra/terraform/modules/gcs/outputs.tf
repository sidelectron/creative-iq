output "bucket_names" {
  value = {
    raw_ads      = google_storage_bucket.raw_ads.name
    extracted    = google_storage_bucket.extracted.name
    models       = google_storage_bucket.models.name
    brand_assets = google_storage_bucket.brand_assets.name
  }
}
