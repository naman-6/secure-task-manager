"""
main.py
Secure Task & Asset Manager - Backend API

FastAPI application exposing a REST CRUD interface for Task/Asset records.
Includes:
  - Structured JSON logging (stdout) suitable for aggregation (EFK/ELK/Loki).
  - Pydantic-based request validation (see schemas.py).
  - Liveness (/healthz) and readiness (/ready) probes for Kubernetes.
  - CORS restricted via environment-configurable allowed origins.
"""

import json
import logging
import os
import sys
import time
import uuid
from typing import List, Optional
from prometheus_fastapi_instrumentator import Instrumentator

from fastapi import FastAPI, Depends, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import models
import schemas
from database import Base, engine, get_db, wait_for_db

# ---------------------------------------------------------------------------
# Structured JSON logging configuration
# ---------------------------------------------------------------------------


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        extra_fields = getattr(record, "extra_fields", None)
        if extra_fields:
            payload.update(extra_fields)
        return json.dumps(payload)


def configure_logging() -> logging.Logger:
    root_logger = logging.getLogger()
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    root_logger.setLevel(log_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    # Avoid duplicate handlers on reload
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Tame overly chatty third-party loggers but keep them structured.
    logging.getLogger("uvicorn.access").setLevel(log_level)
    logging.getLogger("uvicorn.error").setLevel(log_level)

    return logging.getLogger("app")


logger = configure_logging()

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

APP_NAME = "secure-task-manager-backend"
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")

app = FastAPI(
    title="Secure Task & Asset Manager API",
    description="A secure REST API for managing tasks and assets.",
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

Instrumentator().instrument(app).expose(app)

# CORS: restrict to explicitly allowed origins (comma-separated env var).
# Defaults to the in-cluster frontend NodePort access patterns for local dev.
_raw_origins = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
ALLOWED_ORIGINS = [origin.strip() for origin in _raw_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request logging / correlation ID middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    start_time = time.time()

    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        status_code = response.status_code if response is not None else 500
        logger.info(
            "request_handled",
            extra={
                "extra_fields": {
                    "correlation_id": correlation_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "client_ip": request.client.host if request.client else None,
                }
            },
        )
        if response is not None:
            response.headers["X-Correlation-ID"] = correlation_id


# ---------------------------------------------------------------------------
# Startup / Shutdown
# ---------------------------------------------------------------------------
@app.on_event("startup")
def on_startup() -> None:
    logger.info("Starting up %s v%s", APP_NAME, APP_VERSION)
    wait_for_db()
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema verified/created.")


@app.on_event("shutdown")
def on_shutdown() -> None:
    logger.info("Shutting down %s", APP_NAME)


# ---------------------------------------------------------------------------
# Health / Readiness probes
# ---------------------------------------------------------------------------
@app.get("/healthz", response_model=schemas.HealthResponse, tags=["Health"])
def healthz():
    """
    Liveness probe. Returns 200 as long as the process is running and able
    to handle HTTP requests. Does NOT check downstream dependencies.
    """
    return schemas.HealthResponse(status="ok", service=APP_NAME)


@app.get("/ready", response_model=schemas.ReadinessResponse, tags=["Health"])
def ready(db: Session = Depends(get_db)):
    """
    Readiness probe. Verifies the database connection is usable. Used by
    Kubernetes to decide whether this pod should receive traffic.
    """
    try:
        db.execute(select(1))
        return schemas.ReadinessResponse(status="ready", database="connected")
    except SQLAlchemyError as exc:
        logger.error("Readiness check failed: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not reachable.",
        )


# ---------------------------------------------------------------------------
# CRUD Endpoints: /api/v1/tasks
# ---------------------------------------------------------------------------
API_PREFIX = "/api/v1"


@app.post(
    f"{API_PREFIX}/tasks",
    response_model=schemas.TaskResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Tasks"],
)
def create_task(payload: schemas.TaskCreate, db: Session = Depends(get_db)):
    task = models.Task(
        title=payload.title,
        description=payload.description,
        asset_tag=payload.asset_tag,
        status=payload.status.value,
        priority=payload.priority.value,
        owner=payload.owner,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    logger.info("task_created", extra={"extra_fields": {"task_id": str(task.id)}})
    return task


@app.get(
    f"{API_PREFIX}/tasks",
    response_model=List[schemas.TaskResponse],
    tags=["Tasks"],
)
def list_tasks(
    db: Session = Depends(get_db),
    status_filter: Optional[schemas.TaskStatus] = Query(None, alias="status"),
    priority_filter: Optional[schemas.TaskPriority] = Query(None, alias="priority"),
    search: Optional[str] = Query(None, max_length=200),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    query = db.query(models.Task)

    if status_filter is not None:
        query = query.filter(models.Task.status == status_filter.value)
    if priority_filter is not None:
        query = query.filter(models.Task.priority == priority_filter.value)
    if search:
        like_pattern = f"%{search.strip()}%"
        query = query.filter(models.Task.title.ilike(like_pattern))

    tasks = (
        query.order_by(models.Task.created_at.desc()).offset(skip).limit(limit).all()
    )
    return tasks


@app.get(
    f"{API_PREFIX}/tasks/{{task_id}}",
    response_model=schemas.TaskResponse,
    tags=["Tasks"],
)
def get_task(task_id: uuid.UUID, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return task


@app.put(
    f"{API_PREFIX}/tasks/{{task_id}}",
    response_model=schemas.TaskResponse,
    tags=["Tasks"],
)
def update_task(task_id: uuid.UUID, payload: schemas.TaskUpdate, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(value, "value"):  # Enum -> raw string for storage
            value = value.value
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    logger.info("task_updated", extra={"extra_fields": {"task_id": str(task.id)}})
    return task


@app.delete(
    f"{API_PREFIX}/tasks/{{task_id}}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Tasks"],
)
def delete_task(task_id: uuid.UUID, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    db.delete(task)
    db.commit()
    logger.info("task_deleted", extra={"extra_fields": {"task_id": str(task_id)}})
    return None


@app.get("/", tags=["Root"])
def root():
    return {"service": APP_NAME, "version": APP_VERSION, "status": "running"}
