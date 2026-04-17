"""Application settings loaded from environment (Pydantic Settings)."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for CreativeIQ services."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    api_v1_prefix: str = Field(default="/api/v1", validation_alias="API_V1_PREFIX")
    cors_origins: str = Field(
        default="http://localhost:3000",
        validation_alias="CORS_ORIGINS",
        description="Comma-separated list of allowed CORS origins.",
    )
    api_service_name: str = Field(default="api", validation_alias="API_SERVICE_NAME")

    # Database
    database_url: str = Field(validation_alias="DATABASE_URL")
    database_read_replica_url: str | None = Field(
        default=None, validation_alias="DATABASE_READ_REPLICA_URL"
    )

    # Redis
    redis_url: str = Field(validation_alias="REDIS_URL")
    redis_events_stream: str = Field(
        default="creativeiq:events", validation_alias="REDIS_EVENTS_STREAM"
    )

    # Storage
    gcs_project_id: str = Field(default="", validation_alias="GCS_PROJECT_ID")
    storage_bucket_raw_ads: str = Field(validation_alias="STORAGE_BUCKET_RAW_ADS")
    storage_bucket_extracted: str = Field(validation_alias="STORAGE_BUCKET_EXTRACTED")
    storage_bucket_models: str = Field(validation_alias="STORAGE_BUCKET_MODELS")
    storage_bucket_brand_assets: str = Field(validation_alias="STORAGE_BUCKET_BRAND_ASSETS")
    minio_endpoint_url: str = Field(default="", validation_alias="MINIO_ENDPOINT_URL")
    minio_access_key: str = Field(default="", validation_alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(default="", validation_alias="MINIO_SECRET_KEY")
    minio_region: str = Field(default="us-east-1", validation_alias="MINIO_REGION")
    minio_use_ssl: bool = Field(default=False, validation_alias="MINIO_USE_SSL")

    # Gemini
    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")
    gemini_model_pro: str = Field(default="gemini-2.5-pro", validation_alias="GEMINI_MODEL_PRO")
    gemini_model_flash: str = Field(
        default="gemini-2.5-flash", validation_alias="GEMINI_MODEL_FLASH"
    )
    gemini_embedding_model: str = Field(
        default="text-embedding-004", validation_alias="GEMINI_EMBEDDING_MODEL"
    )
    gemini_cache_enabled: bool = Field(
        default=True, validation_alias="GEMINI_CACHE_ENABLED"
    )
    gemini_input_usd_per_1m_tokens: float = Field(
        default=0.0, validation_alias="GEMINI_INPUT_USD_PER_1M_TOKENS"
    )
    gemini_output_usd_per_1m_tokens: float = Field(
        default=0.0, validation_alias="GEMINI_OUTPUT_USD_PER_1M_TOKENS"
    )

    # Decomposition / worker
    transcription_method: str = Field(
        default="whisper",
        validation_alias="TRANSCRIPTION_METHOD",
        description='Transcription backend: "whisper" or "gemini".',
    )
    decomposition_metrics_port: int = Field(
        default=9100, validation_alias="DECOMPOSITION_METRICS_PORT"
    )
    profile_engine_metrics_port: int = Field(
        default=9101, validation_alias="PROFILE_ENGINE_METRICS_PORT"
    )

    # Snowflake (Phase 3+)
    snowflake_account: str = Field(default="", validation_alias="SNOWFLAKE_ACCOUNT")
    snowflake_user: str = Field(default="", validation_alias="SNOWFLAKE_USER")
    snowflake_password: str = Field(default="", validation_alias="SNOWFLAKE_PASSWORD")
    snowflake_database: str = Field(
        default="creative_intelligence", validation_alias="SNOWFLAKE_DATABASE"
    )
    snowflake_schema_raw: str = Field(default="raw", validation_alias="SNOWFLAKE_SCHEMA_RAW")
    snowflake_warehouse: str = Field(default="", validation_alias="SNOWFLAKE_WAREHOUSE")
    snowflake_role: str = Field(default="", validation_alias="SNOWFLAKE_ROLE")

    # Auth
    jwt_secret_key: str = Field(validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(
        default=15, validation_alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    jwt_refresh_token_expire_minutes: int = Field(
        default=10080, validation_alias="JWT_REFRESH_TOKEN_EXPIRE_MINUTES"
    )
    admin_emails: str = Field(default="", validation_alias="ADMIN_EMAILS")
    chat_history_window: int = Field(default=20, validation_alias="CHAT_HISTORY_WINDOW")
    chat_tool_call_limit: int = Field(default=5, validation_alias="CHAT_TOOL_CALL_LIMIT")
    chat_response_target_words_min: int = Field(
        default=200, validation_alias="CHAT_RESPONSE_TARGET_WORDS_MIN"
    )
    chat_response_target_words_max: int = Field(
        default=400, validation_alias="CHAT_RESPONSE_TARGET_WORDS_MAX"
    )
    chat_context_timeout_ms: int = Field(default=500, validation_alias="CHAT_CONTEXT_TIMEOUT_MS")

    @field_validator("minio_use_ssl", mode="before")
    @classmethod
    def parse_bool(cls, v: object) -> bool:
        if isinstance(v, bool):
            return v
        if v is None:
            return False
        s = str(v).strip().lower()
        return s in ("1", "true", "yes", "on")

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def admin_email_list(self) -> list[str]:
        return [v.strip().lower() for v in self.admin_emails.split(",") if v.strip()]

    def database_url_sync(self) -> str:
        """Sync SQLAlchemy URL for Celery worker (psycopg2)."""
        u = self.database_url
        if "+asyncpg" in u:
            return u.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
        return u


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
