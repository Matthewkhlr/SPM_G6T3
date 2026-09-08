from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./registration.db"
    cors_origin: str = "http://localhost:5173"
    event_service_url: str = "http://localhost:8002"


settings = Settings()
