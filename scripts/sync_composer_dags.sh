#!/usr/bin/env bash
set -euo pipefail

# Sync local DAGs to the Composer environment DAG bucket (GCS).
# Example:
#   export COMPOSER_DAG_URI="gs://us-east1-env-abc123-bucket/dags"
#   ./scripts/sync_composer_dags.sh
#
# Obtain COMPOSER_DAG_URI from Terraform output composer_dags_bucket or the Composer UI.

if [[ -z "${COMPOSER_DAG_URI:-}" ]]; then
  echo "Set COMPOSER_DAG_URI to the gs://.../dags prefix from your Composer environment." >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
gsutil -m rsync -r -c -d "${ROOT}/airflow/dags" "${COMPOSER_DAG_URI}"
