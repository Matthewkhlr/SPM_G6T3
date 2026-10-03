from shared.config.settings import ServiceSettings


class Settings(ServiceSettings):
    database_url: str = "mysql+pymysql://connectsphere:connectsphere@127.0.0.1:3307/registration"
    event_service_url: str = "http://127.0.0.1:8002"
    user_service_url: str = "http://127.0.0.1:8001"
    notification_service_url: str = "http://127.0.0.1:8006"


settings = Settings()
