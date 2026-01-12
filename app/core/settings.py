from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # Database
    database_url: str = "postgresql://agentops:agentops_password@localhost:5432/agentops"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # API
    app_env: str = "development"
    app_ingest_secret: str = ""
    log_level: str = "INFO"

    # LLM
    openai_api_key: str = ""

    # RQ
    rq_queue_name: str = "rca"

    # CORS - for Next.js UI and browser clients
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"

    def get_cors_origins(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
