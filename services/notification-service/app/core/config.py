from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "mysql+pymysql://connectsphere:connectsphere@localhost:3312/notification"
    cors_origin: str = "http://localhost:5173"


settings = Settings()
