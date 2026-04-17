#!/usr/bin/env bash
# Provision CreativeIQ *dev* stack in GCP (VPC, GKE, Cloud SQL, Redis, GCS, AR, IAM).
#
# Run from repo root in Google Cloud Shell or any Linux/macOS host with:
#   - gcloud (authenticated: gcloud auth login && gcloud auth application-default login)
#   - terraform >= 1.6
#   - Billing enabled on the project; your user needs roles to create networks, GKE, SQL, etc.
#
# Usage (from repository root):
#   bash scripts/terraform_apply_dev_gcp.sh
#
# Optional env:
#   TF_STATE_BUCKET   — override GCS bucket for Terraform state (default: <project_id>-tf-state)
#   TF_STATE_PREFIX   — override state prefix (default: terraform/state/dev)
#   TF_AUTO_APPROVE=0 — set to skip -auto-approve (script will prompt)
#   TF_VAR_terraform_deployer_email — e.g. creativeiq@PROJECT.iam.gserviceaccount.com for AR writer IAM

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT}/infra/terraform"
TFVARS="${TF_DIR}/environments/dev/terraform.tfvars"

if [[ ! -f "${TFVARS}" ]]; then
  echo "Missing ${TFVARS}" >&2
  exit 1
fi

# Git Bash / MSYS: Terraform MSI installs to "C:\Program Files\Terraform" but that dir is often
# missing from the PATH Git Bash inherits. Prepend standard locations so `terraform` resolves.
_terraform_on_path() { command -v terraform >/dev/null 2>&1 || command -v terraform.exe >/dev/null 2>&1; }
if ! _terraform_on_path; then
  case "$(uname -s 2>/dev/null)" in
    MINGW*|MSYS*|CYGWIN*)
      for d in "/c/Program Files/Terraform" "/c/Program Files (x86)/Terraform"; do
        if [[ -x "$d/terraform.exe" ]]; then
          export PATH="$d:$PATH"
          break
        fi
      done
      ;;
  esac
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud not found. Install Google Cloud SDK, or use Cloud Shell: https://shell.cloud.google.com" >&2
  exit 1
fi
if ! _terraform_on_path; then
  echo "terraform not found on PATH." >&2
  echo "  Windows: install MSI from https://developer.hashicorp.com/terraform/install" >&2
  echo "  Or (PowerShell as Admin): winget install Hashicorp.Terraform" >&2
  echo "  Or use Google Cloud Shell (Terraform preinstalled): https://shell.cloud.google.com" >&2
  exit 1
fi

# shellcheck disable=SC2002
PROJECT_ID="$(grep -E '^[[:space:]]*project_id[[:space:]]*=' "${TFVARS}" | head -1 | sed -E 's/^[[:space:]]*project_id[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/')"
REGION="$(grep -E '^[[:space:]]*region[[:space:]]*=' "${TFVARS}" | head -1 | sed -E 's/^[[:space:]]*region[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/')"

if [[ -z "${PROJECT_ID}" || -z "${REGION}" ]]; then
  echo "Could not parse project_id / region from ${TFVARS}" >&2
  exit 1
fi

CLUSTER_NAME="$(grep -E '^[[:space:]]*cluster_name[[:space:]]*=' "${TFVARS}" | head -1 | sed -E 's/^[[:space:]]*cluster_name[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/')"
CLUSTER_NAME="${CLUSTER_NAME:-creativeiq-gke-dev}"

BUCKET="${TF_STATE_BUCKET:-${PROJECT_ID}-tf-state}"
PREFIX="${TF_STATE_PREFIX:-terraform/state/dev}"

echo "==> Project: ${PROJECT_ID}"
echo "==> Region:  ${REGION}"
echo "==> State:   gs://${BUCKET}  prefix=${PREFIX}"
echo ""

gcloud config set project "${PROJECT_ID}" >/dev/null

echo "==> Enabling required Google APIs (idempotent)..."
gcloud services enable \
  compute.googleapis.com \
  container.googleapis.com \
  servicenetworking.googleapis.com \
  sqladmin.googleapis.com \
  redis.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  artifactregistry.googleapis.com \
  storage.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com \
  cloudresourcemanager.googleapis.com \
  --project="${PROJECT_ID}"

echo "==> Terraform state bucket..."
if gsutil ls -b "gs://${BUCKET}" >/dev/null 2>&1; then
  echo "    Bucket gs://${BUCKET} already exists."
else
  gsutil mb -p "${PROJECT_ID}" -l "${REGION}" "gs://${BUCKET}/"
  echo "    Created gs://${BUCKET}"
fi
gsutil versioning set on "gs://${BUCKET}/" >/dev/null

BACKEND_HCL="${TF_DIR}/backend.hcl"
cat >"${BACKEND_HCL}" <<EOF
bucket = "${BUCKET}"
prefix = "${PREFIX}"
EOF
echo "==> Wrote ${BACKEND_HCL} (do not commit; see .gitignore)"

cd "${TF_DIR}"

echo "==> terraform init..."
terraform init -backend-config=backend.hcl -input=false

APPLY_ARGS=(-var-file=environments/dev/terraform.tfvars -input=false)
if [[ "${TF_AUTO_APPROVE:-1}" != "0" ]]; then
  APPLY_ARGS+=(-auto-approve)
fi

echo "==> terraform apply ${APPLY_ARGS[*]}"
echo "    (GKE + Cloud SQL often takes 20–40 minutes on first apply)"
terraform apply "${APPLY_ARGS[@]}"

echo ""
echo "Done. In Console: Kubernetes Engine → Clusters → expect ${CLUSTER_NAME} in ${REGION}."
echo "Then re-run GitHub Actions deploy."
