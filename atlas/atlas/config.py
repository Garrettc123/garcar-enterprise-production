from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    dry_run: bool = os.getenv("ATLAS_DRY_RUN", "true").lower() in {"1", "true", "yes"}
    sku_audit: str = os.getenv(
        "SKU_AUDIT", "https://buy.stripe.com/dRm8wPbb72pY2Mz8BR43S1D"
    )
    sku_sprint: str = os.getenv(
        "SKU_SPRINT", "https://buy.stripe.com/aFa8wPdjfggO3QDcS743S1F"
    )
    storefront: str = os.getenv("STOREFRONT", "https://garrettc123.github.io/")
    operator_email: str = os.getenv("OPERATOR_EMAIL", "garrett@garcar.io")


settings = Settings()
