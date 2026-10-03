from shared.config.settings import ServiceSettings


class Settings(ServiceSettings):
    database_url: str = "mysql+pymysql://connectsphere:connectsphere@127.0.0.1:3307/notification"
    user_service_url: str = "http://127.0.0.1:8001"


settings = Settings()
