from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    log_level: str
    fail_risk_once: bool
    fail_credit_randomly: bool
    crash_after_executor: str
    crash_after_step_or_superstep: str
    retry_max_attempts: int
    retry_base_delay_ms: int
    retry_jitter_ms: int
    azure_ai_project_id: str
    azure_ai_project_name: str
    foundry_model_deployment_name: str
    azure_openai_endpoint: str
    azure_openai_api_key: str
    database_url: str = ""
    db_auth_mode: str = "password"
    db_sslmode: str = "prefer"
    db_schema_managed_externally: bool = False
    azure_client_id: str = ""
    azure_ai_project_endpoint: str = ""
    foundry_responses_endpoint: str = ""
    foundry_hosted_agent_name: str = "underwriting-hosted"
    foundry_hosted_agent_version: str = ""
    foundry_responses_timeout_seconds: float = 60.0
    frontend_origin: str = "http://localhost:5173"
    execution_mode: str = "hosted"
    db_pool_min_size: int = 0
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_recycle_seconds: int = 1800
    local_review_mutation_enabled: bool = False
    local_review_actor_id: str = ""

    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?sslmode={self.db_sslmode}"
        )


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, minimum: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if parsed < minimum:
        raise RuntimeError(f"{name} must be at least {minimum}")
    return parsed


def _uses_hosted_database_pool() -> bool:
    app_env = os.getenv("APP_ENV", "").strip().lower()
    return app_env.startswith(("aca", "foundry")) or _env_bool("DB_SCHEMA_MANAGED_EXTERNALLY")


def _env_int_with_alias(
    name: str,
    alias: str,
    default: int,
    *,
    minimum: int,
) -> int:
    if os.getenv(name) is not None:
        return _env_int(name, default, minimum=minimum)
    return _env_int(alias, default, minimum=minimum)


def load_settings() -> Settings:
    load_dotenv()
    hosted_database_pool = _uses_hosted_database_pool()
    execution_mode = os.getenv("UNDERWRITING_EXECUTION_MODE", "hosted").strip().lower()
    local_review_mutation_enabled = _env_bool("ENABLE_LOCAL_REVIEW_MUTATION")
    local_review_actor_id = os.getenv("LOCAL_REVIEW_ACTOR_ID", "").strip()
    if local_review_mutation_enabled and (execution_mode != "local" or hosted_database_pool):
        raise RuntimeError(
            "ENABLE_LOCAL_REVIEW_MUTATION is allowed only for non-hosted local execution"
        )
    if local_review_mutation_enabled and not local_review_actor_id:
        raise RuntimeError(
            "LOCAL_REVIEW_ACTOR_ID is required when local review mutation is enabled"
        )
    pool_min_size = _env_int("DB_POOL_MIN_SIZE", 0, minimum=0)
    if pool_min_size != 0:
        raise RuntimeError(
            "DB_POOL_MIN_SIZE must be 0 because SQLAlchemy QueuePool opens connections lazily"
        )
    return Settings(
        db_host=os.getenv("DB_HOST", "localhost"),
        db_port=int(os.getenv("DB_PORT", "5432")),
        db_name=os.getenv("DB_NAME", "underwriting"),
        db_user=os.getenv("DB_USER", "underwriting"),
        db_password=os.getenv("DB_PASSWORD", "underwriting"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        fail_risk_once=_env_bool("FAIL_RISK_ONCE"),
        fail_credit_randomly=_env_bool("FAIL_CREDIT_RANDOMLY"),
        crash_after_executor=os.getenv("CRASH_AFTER_EXECUTOR", ""),
        crash_after_step_or_superstep=os.getenv("CRASH_AFTER_STEP_OR_SUPERSTEP", ""),
        retry_max_attempts=int(os.getenv("RETRY_MAX_ATTEMPTS", "3")),
        retry_base_delay_ms=int(os.getenv("RETRY_BASE_DELAY_MS", "200")),
        retry_jitter_ms=int(os.getenv("RETRY_JITTER_MS", "100")),
        azure_ai_project_id=os.getenv("AZURE_AI_PROJECT_ID", ""),
        azure_ai_project_name=os.getenv("AZURE_AI_PROJECT_NAME", ""),
        foundry_model_deployment_name=os.getenv(
            "UNDERWRITING_MODEL_DEPLOYMENT_NAME",
            os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", ""),
        ),
        azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
        azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
        database_url=os.getenv("DATABASE_URL", ""),
        db_auth_mode=os.getenv("DB_AUTH_MODE", "password"),
        db_sslmode=os.getenv("DB_SSLMODE", "prefer"),
        db_schema_managed_externally=_env_bool("DB_SCHEMA_MANAGED_EXTERNALLY"),
        azure_client_id=os.getenv("AZURE_CLIENT_ID", ""),
        azure_ai_project_endpoint=os.getenv("AZURE_AI_PROJECT_ENDPOINT", ""),
        foundry_responses_endpoint=os.getenv("FOUNDRY_RESPONSES_ENDPOINT", ""),
        foundry_hosted_agent_name=os.getenv("FOUNDRY_HOSTED_AGENT_NAME", "underwriting-hosted"),
        foundry_hosted_agent_version=os.getenv("FOUNDRY_HOSTED_AGENT_VERSION", ""),
        foundry_responses_timeout_seconds=float(
            os.getenv("FOUNDRY_RESPONSES_TIMEOUT_SECONDS", "60")
        ),
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").rstrip("/"),
        execution_mode=execution_mode,
        db_pool_min_size=pool_min_size,
        db_pool_size=_env_int_with_alias(
            "DB_POOL_MAX_SIZE",
            "DB_POOL_SIZE",
            2 if hosted_database_pool else 5,
            minimum=1,
        ),
        db_max_overflow=_env_int(
            "DB_MAX_OVERFLOW",
            0 if hosted_database_pool else 10,
            minimum=0,
        ),
        db_pool_recycle_seconds=_env_int_with_alias(
            "DB_POOL_MAX_IDLE_SECONDS",
            "DB_POOL_RECYCLE_SECONDS",
            30 if hosted_database_pool else 1800,
            minimum=1,
        ),
        local_review_mutation_enabled=local_review_mutation_enabled,
        local_review_actor_id=local_review_actor_id,
    )
