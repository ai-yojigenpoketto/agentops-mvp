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


settings = Settings()
