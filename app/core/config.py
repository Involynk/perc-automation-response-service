from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres_password@localhost:5432/perc_db"
    ENVIRONMENT: str = "development"
    # Query understanding provider selection: 'mock' for deterministic tests, 'llm' for production
    QUERY_UNDERSTANDING_PROVIDER: str = "mock"

    # LLM provider configuration (used when QUERY_UNDERSTANDING_PROVIDER == 'llm')
    LLM_PROVIDER: str | None = None
    LLM_MODEL: str | None = None
    LLM_TEMPERATURE: float | None = 0.0
    # Ollama-specific configuration
    OLLAMA_BASE_URL: str | None = "http://localhost:11434"
    OLLAMA_MODEL: str | None = "qwen3:8b"
    OLLAMA_TIMEOUT: int | None = 180

    # Meta WhatsApp Cloud API configuration
    META_ACCESS_TOKEN: str | None = None
    META_APP_SECRET: str | None = None
    WABA_ID: str | None = None
    PHONE_NUMBER_ID: str | None = None
    GRAPH_API_VERSION: str = "v26.0"
    WEBHOOK_VERIFY_TOKEN: str = "perc_webhook_secret_token"

    # Internal Microservices Authentication
    INTERNAL_SERVICE_API_KEY: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("DATABASE_URL environment variable must not be empty.")
        return v.strip()


settings = Settings()
