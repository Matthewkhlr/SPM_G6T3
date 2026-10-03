from shared.config.settings import ServiceSettings


class Settings(ServiceSettings):
    database_url: str = "mysql+pymysql://connectsphere:connectsphere@127.0.0.1:3307/user"


settings = Settings()
