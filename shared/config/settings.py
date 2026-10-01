"""Settings every microservice shares.

Each service subclasses this and supplies its own database URL, plus any
URLs or numbers that belong only to that service.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    # Comma-separated; browsers treat localhost and 127.0.0.1 as distinct origins.
    cors_origin: str = "http://localhost:5173,http://127.0.0.1:5173"
