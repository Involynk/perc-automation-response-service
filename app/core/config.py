from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres_password@localhost:5432/perc_db"
    ENVIRONMENT: str = "development"
    # LLM provider configuration (Groq)
    LLM_PROVIDER: str | None = "groq"
    LLM_BASE_URL: str | None = "https://api.groq.com/openai/v1"
    LLM_API_KEY: str | None = None
    LLM_MODEL: str | None = "llama-3.3-70b-versatile"
    LLM_TEMPERATURE: float | None = 0.0
    LLM_TIMEOUT: int | None = 30
    QUERY_UNDERSTANDING_PROVIDER: str | None = None
    OLLAMA_BASE_URL: str | None = "http://localhost:11434"
    OLLAMA_MODEL: str | None = "qwen3:8b"
    OLLAMA_TIMEOUT: int | None = 15


    # Meta WhatsApp Cloud API configuration (optional / direct outbound)
    META_ACCESS_TOKEN: str | None = None
    META_APP_SECRET: str | None = None
    WABA_ID: str | None = None
    PHONE_NUMBER_ID: str | None = None
    GRAPH_API_VERSION: str = "v26.0"
    WEBHOOK_VERIFY_TOKEN: str = "perc_webhook_secret_token"

    # Internal Microservices Authentication
    INTERNAL_SERVICE_API_KEY: str | None = None

    # Kafka Event Streaming Configuration
    KAFKA_BROKERS: str | None = None
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_CLIENT_ID: str = "perc-response-service"
    KAFKA_GROUP_ID: str = "perc-response-service-group"
    KAFKA_USE_SSL: bool = False
    KAFKA_SASL_MECHANISM: str | None = None
    KAFKA_SASL_USERNAME: str | None = None
    KAFKA_SASL_PASSWORD: str | None = None

    # Inbound Topics
    KAFKA_TOPIC_LEAD_EVENTS: str = "perc.lead-events"
    KAFKA_TOPIC_ACTION_REQUIRED: str = "perc.followup.action-required"
    KAFKA_TOPIC_MEETING_EVENTS: str = "perc.meeting-events"

    # Outbound Topics
    KAFKA_TOPIC_RESPONSE_SENT: str = "perc.response.sent"
    KAFKA_TOPIC_FOLLOWUP_SENT: str = "perc.followup.sent"
    KAFKA_TOPIC_MEETING_CREATE_REQUESTED: str = "perc.meeting.create-requested"

    # Redis Streams for Service Events / Logs
    REDIS_URL: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("DATABASE_URL environment variable must not be empty.")
        return v.strip()


settings = Settings()
