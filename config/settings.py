from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    cassandra_host: str = "localhost"
    cassandra_port: int = 9042
    cassandra_keyspace: str = "flight_delays"
    data_dir: str = ""
    log_dir: str = "logs"

    class Config:
        env_file = ".env"


settings = Settings()