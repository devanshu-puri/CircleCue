from typing import Literal, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ENV: str = "development"
    MONGODB_URI: str = "mongodb://localhost:27017/circlecue"
    JWT_SECRET: str = "super-secret-key-change-in-prod-1234567890"
    TZ_DEFAULT: str = "UTC"
    DEMO_USER_EMAIL: Optional[str] = "arjun@demo.circlecue.app"
    
    # AI Config
    AI_PROVIDER: Literal["openai_compat", "ollama", "rules"] = "rules"
    AI_BASE_URL: str = "http://localhost:11434/v1"
    AI_MODEL: str = "gemma2:9b"
    AI_API_KEY: Optional[str] = "ollama"
    AI_TIMEOUT_S: float = 8.0
    
    # Temporal Config
    TEMPORAL_ADDRESS: str = "localhost:7233"
    TEMPORAL_NAMESPACE: str = "default"
    TEMPORAL_API_KEY: Optional[str] = None
    TEMPORAL_ENABLED: bool = False
    
    # Monitoring & Extras
    SENTRY_DSN: Optional[str] = None
    DEMO_CLOCK: bool = True
    PREDICTOR_PROVIDER: Literal["tabpfn", "stub"] = "stub"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
