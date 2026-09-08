from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    cors_origin: str = "http://localhost:5173"
    user_service_url: str = "http://localhost:8001"
    event_service_url: str = "http://localhost:8002"
    venue_service_url: str = "http://localhost:8003"
    equipment_service_url: str = "http://localhost:8004"
    registration_service_url: str = "http://localhost:8005"
    notification_service_url: str = "http://localhost:8006"


settings = Settings()
