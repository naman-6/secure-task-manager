"""
database.py
Handles SQLAlchemy engine/session creation for the Secure Task & Asset Manager.
Reads all connection parameters from environment variables so that no
credentials are ever hard-coded in source control.
"""

import os
import time
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

logger = logging.getLogger("database")

# ---------------------------------------------------------------------------
# Environment-driven configuration (populated via ConfigMap / Secret in k8s,
# or via docker-compose environment section for local development).
# ---------------------------------------------------------------------------
POSTGRES_USER = os.getenv("POSTGRES_USER", "taskadmin")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "changeme")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres-service")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "taskmanager")

SQLALCHEMY_DATABASE_URL = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

# pool_pre_ping avoids "server closed the connection unexpectedly" errors
# after long idle periods (common with k8s services / NAT timeouts).
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=1800,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session and guarantees closure."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def wait_for_db(max_retries: int = 30, delay_seconds: int = 2) -> None:
    """
    Blocks until the database is reachable or max_retries is exhausted.
    Used at application startup so the backend pod does not crash-loop
    while Postgres is still initializing inside the StatefulSet.
    """
    attempt = 0
    while attempt < max_retries:
        try:
            conn = engine.connect()
            conn.close()
            logger.info("Database connection established.")
            return
        except OperationalError as exc:
            attempt += 1
            logger.warning(
                "Database not ready (attempt %s/%s): %s",
                attempt,
                max_retries,
                str(exc).splitlines()[0],
            )
            time.sleep(delay_seconds)
    raise RuntimeError("Could not connect to the database after maximum retries.")
