"""CLI entrypoint for PostgreSQL -> Snowflake sync."""

from __future__ import annotations

import argparse

from services.ingestion.sync_service import TableKey, check_snowflake, run_sync
from services.api.app.logging_config import configure_logging
from shared.config.settings import settings


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Postgres tables into Snowflake RAW schema")
    parser.add_argument(
        "--table",
        choices=["ads", "ad_performance", "creative_fingerprints", "all"],
        default="all",
    )
    parser.add_argument("--mode", choices=["full", "incremental"], default="incremental")
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    configure_logging(service_name="ingestion-sync", log_level=settings.log_level)
    check_snowflake()
    if args.check_only:
        print("Snowflake connectivity check passed.")
        return

    tables: list[TableKey] = (
        ["ads", "ad_performance", "creative_fingerprints"]
        if args.table == "all"
        else [args.table]
    )
    for table in tables:
        result = run_sync(table=table, mode=args.mode)
        print(
            f"{result.table}: mode={result.mode} read={result.records_read} "
            f"written={result.records_written} synced_at={result.last_synced_at}"
        )


if __name__ == "__main__":
    main()
