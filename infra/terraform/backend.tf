# Remote state: create bucket + versioning first (see docs/DEPLOYMENT_SETUP.md).
# Initialize with: terraform init -backend-config=backend.hcl
terraform {
  backend "gcs" {}
}
