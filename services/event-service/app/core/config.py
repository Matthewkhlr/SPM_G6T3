from shared.config.settings import ServiceSettings


class Settings(ServiceSettings):
    database_url: str = "mysql+pymysql://connectsphere:connectsphere@127.0.0.1:3307/event"
    user_service_url: str = "http://127.0.0.1:8001"
    venue_service_url: str = "http://127.0.0.1:8003"
    equipment_service_url: str = "http://127.0.0.1:8004"
    registration_service_url: str = "http://127.0.0.1:8005"
    notification_service_url: str = "http://127.0.0.1:8006"
    # A proposed date this many days out or less is flagged in the review
    # queue. Single source: read from here, not re-hard-coded per screen.
    event_proposed_date_near_days: int = 14


settings = Settings()
