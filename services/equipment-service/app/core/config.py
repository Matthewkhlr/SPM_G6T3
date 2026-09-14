from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "mysql+pymysql://connectsphere:connectsphere@localhost:3310/equipment"
    # Comma-separated; browsers treat localhost and 127.0.0.1 as distinct origins.
    cors_origin: str = "http://localhost:5173,http://127.0.0.1:5173"
    user_service_url: str = "http://localhost:8001"


settings = Settings()
