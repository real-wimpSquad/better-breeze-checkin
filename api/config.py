from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    breeze_api_key: str
    breeze_subdomain: str = "connectionpointchurch"
    printer_name: str = "DYMO_LabelWriter_550"

    # Optional: Breeze auth for user login
    breeze_oauth_client_id: Optional[str] = None
    breeze_oauth_client_secret: Optional[str] = None

    class Config:
        env_file = ".env"
        env_prefix = "CHECKIN_"


@lru_cache
def get_settings() -> Settings:
    return Settings()
