"""Centralized configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings populated from .env / environment."""

    cassandra_host: str = "127.0.0.1"
    cassandra_port: int = 9042
    keyspace: str = "datawarehousesproject"
    server_host: str = "0.0.0.0"
    server_port: int = 8083
    nasdaq_api_key: str = ""
    llm_base_url: str = "http://localhost:8079"
    llm_model: str = "local"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
