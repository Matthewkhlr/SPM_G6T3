from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "mysql+pymysql://connectsphere:connectsphere@localhost:3311/registration"
    cors_origin: str = "http://localhost:5173"
    event_service_url: str = "http://localhost:8002"


settings = Settings()
