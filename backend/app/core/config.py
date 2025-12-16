"""
Application configuration using Pydantic Settings
Handles all environment variables and application settings
"""

from functools import lru_cache
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application
    app_name: str = "Planning Precedent AI"
    app_env: str = "development"
    debug: bool = False
    secret_key: str = Field(..., min_length=32)
    api_v1_prefix: str = "/api/v1"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4

    # Supabase
    supabase_url: str = Field(...)
    supabase_key: str = Field(...)
    supabase_service_key: str = Field(...)
    database_url: str = Field(...)

    # OpenAI
    openai_api_key: str = Field(...)
    openai_embedding_model: str = "text-embedding-3-large"
    openai_llm_model: str = "gpt-4o"
    openai_max_tokens: int = 4096
    openai_temperature: float = 0.1

    # AWS
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "eu-west-2"
    use_aws_textract: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Scraper
    camden_portal_url: str = "https://camdocs.camden.gov.uk/HPRMWebDrawer/PlanRec"
    scrape_rate_limit: float = 2.0
    scrape_max_concurrent: int = 3
    scrape_start_date: str = "2015-01-01"
    scrape_end_date: str = "2024-12-31"

    # Target Wards
    target_wards: str = "Hampstead Town,Belsize,Frognal,Swiss Cottage"

    # Document Processing
    chunk_size: int = 500
    chunk_overlap: int = 50
    max_chunks_per_document: int = 100

    # Rate Limiting
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 500

    # CORS
    cors_origins: str = "http://localhost:3000"
    cors_allow_credentials: bool = True

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Sentry
    sentry_dsn: Optional[str] = None

    # Feature Flags
    enable_ocr: bool = True
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600

    # UK Specific
    uk_timezone: str = "Europe/London"
    date_format: str = "%d/%m/%Y"

    @field_validator('app_env')
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        """Validate app_env is a known environment"""
        allowed = ['development', 'staging', 'production', 'test']
        if v.lower() not in allowed:
            raise ValueError(f'app_env must be one of: {allowed}')
        return v.lower()

    @field_validator('cors_origins')
    @classmethod
    def validate_cors_origins(cls, v: str) -> str:
        """Validate CORS origins are valid URLs"""
        import re
        origins = [o.strip() for o in v.split(',')]
        url_pattern = re.compile(r'^https?://[^\s/$.?#].[^\s]*$')
        for origin in origins:
            if origin != '*' and not url_pattern.match(origin):
                raise ValueError(f'Invalid CORS origin URL: {origin}')
        return v

    @field_validator('openai_temperature')
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature is within valid range"""
        if not 0.0 <= v <= 2.0:
            raise ValueError('openai_temperature must be between 0.0 and 2.0')
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def target_wards_list(self) -> List[str]:
        """Parse target wards from comma-separated string"""
        return [ward.strip() for ward in self.target_wards.split(",")]

    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.app_env.lower() == "production"

    @property
    def embedding_dimensions(self) -> int:
        """Get embedding dimensions based on model"""
        dimensions_map = {
            "text-embedding-3-large": 3072,
            "text-embedding-3-small": 1536,
            "text-embedding-ada-002": 1536
        }
        return dimensions_map.get(self.openai_embedding_model, 1536)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
