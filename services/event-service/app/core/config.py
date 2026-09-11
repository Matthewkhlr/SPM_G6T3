from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "mysql+pymysql://connectsphere:connectsphere@localhost:3309/event"
    # Comma-separated; browsers treat localhost and 127.0.0.1 as distinct origins.
    cors_origin: str = "http://localhost:5173,http://127.0.0.1:5173"
    user_service_url: str = "http://localhost:8001"
    venue_service_url: str = "http://localhost:8003"
    equipment_service_url: str = "http://localhost:8004"
    registration_service_url: str = "http://localhost:8005"
    notification_service_url: str = "http://localhost:8006"


settings = Settings()
