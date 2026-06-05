#!/usr/bin/env python3
"""Apply Wikis schema and seed data to a Supabase Postgres database."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


MIGRATIONS = [
    Path("migrations/001_production_schema.sql"),
    Path("migrations/002_seed_step02_graph.sql"),
    Path("migrations/003_ingestion_workflow.sql"),
    Path("migrations/004_allow_culture_pillar.sql"),
    Path("migrations/005_ingestion_generation_state.sql"),
    Path("migrations/006_enable_rls.sql"),
]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def validate_database_url(database_url: str | None) -> str:
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    if "YOUR-PASSWORD" in database_url or "[" in database_url or "]" in database_url:
        raise RuntimeError("DATABASE_URL still contains the Supabase dashboard password placeholder")
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("DATABASE_URL must be a Postgres connection string")
    return database_url


def run_psql(database_url: str, sql_file: Path, dry_run: bool) -> None:
    if not sql_file.exists():
        raise RuntimeError(f"missing SQL file: {sql_file}")
    command = ["psql", database_url, "-v", "ON_ERROR_STOP=1", "-f", str(sql_file)]
    if dry_run:
        print(f"would apply {sql_file}")
        return
    print(f"applying {sql_file}")
    subprocess.run(command, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply Wikis migrations and seed data to Supabase.")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--skip-seed-regeneration", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(args.env_file)
    database_url = validate_database_url(args.database_url or os.environ.get("DATABASE_URL"))

    if not args.skip_seed_regeneration:
        subprocess.run(["python3", "scripts/seed_production_db.py"], check=True)

    for migration in MIGRATIONS:
        run_psql(database_url, migration, args.dry_run)

    if not args.dry_run:
        subprocess.run(
            [
                "psql",
                database_url,
                "-v",
                "ON_ERROR_STOP=1",
                "-Atc",
                "select 'topics=' || count(*) from topics;",
            ],
            check=True,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI should produce one clear error.
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
