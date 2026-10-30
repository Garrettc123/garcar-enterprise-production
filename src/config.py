from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")
    environment: str = "development"
    vault_addr: str = "http://127.0.0.1:8200"
    vault_token: str = ""
    vault_mount: str = "secret"
    vault_path: str = "garcar/production/keys"
    s3_ledger_bucket: str = ""
    aws_region: str = "us-east-1"
    ledger_retention_days: int = Field(default=365, ge=1, le=36500)
    stripe_webhook_secret: str = ""
    require_vault: bool = True

@lru_cache
def settings() -> Settings:
    return Settings()
