"""One-shot seed for a fresh hosted database.

Runs the full bootstrap against whatever DATABASE_URL / ANALYST_DATABASE_URL
point at, so a newly provisioned (empty) Postgres comes up fully populated:

    1. init_db            - pgvector extension, read-only role, grants
    2. generate_sample_data - synthetic dataset (deterministic, self-contained)
    3. etl_pipeline       - load into Postgres and apply row-level security
    4. vector_store       - build the NL-to-SQL embeddings

Idempotent: safe to run on every deploy (ETL replaces the tables). Used as the
Render pre-deploy command; can also be run by hand after provisioning a DB.

    python scripts/deploy_seed.py
"""
from __future__ import annotations

import logging

from bizlens.sql import etl_pipeline, vector_store
from scripts import generate_sample_data, init_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("deploy_seed")


def main() -> None:
    log.info("1/4 initialising database (extension, role, grants)")
    init_db.main()

    log.info("2/4 generating synthetic dataset")
    generate_sample_data.generate()

    log.info("3/4 running ETL and applying row-level security")
    etl_pipeline.run()

    log.info("4/4 building NL-to-SQL embeddings")
    vector_store.build()

    log.info("seed complete")


if __name__ == "__main__":
    main()
