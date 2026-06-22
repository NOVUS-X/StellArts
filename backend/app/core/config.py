from __future__ import annotations

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Stellarts"
    DEBUG: bool = False
    STATIC_DIR: str = "static"
    AVATARS_DIR: str = "avatars"
    SUPPORTED_ASSET_CODES: list[str] = ["XLM", "USDC"]

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 3

    # Database
    DATABASE_URL: str

    # Redis (NUEVO)
    REDIS_URL: str = "redis://localhost:6380/0"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6380
    REDIS_DB: int = 0
    NEARBY_CACHE_TTL: int = 60  # Seconds to cache nearby-artisan search results

    # CORS
    BACKEND_CORS_ORIGINS: list[AnyHttpUrl] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str] | str:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        if isinstance(v, list | str):
            return v
        raise ValueError(v)

    # Email (for future use)
    SMTP_TLS: bool = True
    SMTP_PORT: int | None = None
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    # Frontend URL used for verification links
    FRONTEND_URL: str = "http://localhost:3000"
    # Default from address for transactional emails (optional)
    EMAILS_FROM: str | None = None
    # Whether the application requires email verification for protected actions
    REQUIRE_EMAIL_VERIFICATION: bool = True

    # External APIs (for future use)
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_PUBLISHABLE_KEY: str | None = None

    # Google Calendar OAuth
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None

    # Routing Configuration
    ROUTING_PROVIDER: str = "osrm"
    ROUTING_API_URL: str = "http://router.project-osrm.org/route/v1/driving"
    ROUTING_API_KEY: str | None = None

    # Soroban Configuration
    # Optional vision model configuration for completion verification
    VISION_API_URL: str | None = None
    VISION_API_KEY: str | None = None
    VISION_MODEL: str = "gpt-4o-mini"
    JOB_COMPLETION_ACCEPTANCE_THRESHOLD: float = 0.75

    # Vision-to-Scope Ingestion Gateway Configuration
    # Media Storage
    MEDIA_STORAGE_TYPE: str = "local"  # "local" or "s3"
    MEDIA_TEMP_DIR: str = "/tmp/stellarts_media"
    MEDIA_MAX_SIZE_MB: int = 50  # Maximum file size in MB
    MEDIA_MAX_TOTAL_SIZE_MB: int = 100  # Maximum total payload size in MB
    
    # S3 Configuration (if MEDIA_STORAGE_TYPE == "s3")
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET: str | None = None
    AWS_S3_PREFIX: str = "job-ingest/"
    
    # AI Quality Validation Configuration
    AI_VALIDATION_PROVIDER: str = "openai"  # "openai" or "anthropic"
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    AI_VALIDATION_MODEL: str = "gpt-4o"  # or "claude-3-5-sonnet-20241022"
    AI_VALIDATION_TIMEOUT_SECONDS: int = 30
    
    # Allowed media types
    ALLOWED_IMAGE_TYPES: list[str] = ["image/jpeg", "image/png", "image/webp"]
    ALLOWED_VIDEO_TYPES: list[str] = ["video/mp4"]
    ALLOWED_AUDIO_TYPES: list[str] = ["audio/mpeg", "audio/wav", "audio/mp3"]
    
    # Analysis Node Queue Configuration
    ANALYSIS_QUEUE_TYPE: str = "redis"  # "redis" or "sqs"
    ANALYSIS_QUEUE_NAME: str = "job_analysis_queue"
    
    # Stellar/Soroban Configuration
    STELLAR_NETWORK: str = "standalone"  # standalone, testnet, or mainnet
    STELLAR_RPC_URL: str = "http://localhost:8002/soroban/rpc"
    STELLAR_NETWORK_PASSPHRASE: str = "Standalone Network ; September 2022"
    STELLAR_ESCROW_PUBLIC: str | None = None
    ESCROW_CONTRACT_ID: str | None = None
    REPUTATION_CONTRACT_ID: str | None = None

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}


settings = Settings()
