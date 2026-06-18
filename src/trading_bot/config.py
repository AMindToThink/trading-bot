"""Configuration loaded from environment variables (and a local ``.env`` if present).

Secrets are NEVER hardcoded or committed. Copy ``.env.example`` to ``.env`` and fill in
your keys; ``.env`` is gitignored.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    alpaca_api_key: str | None
    alpaca_secret_key: str | None
    alpaca_paper: bool
    alpaca_data_feed: str  # "iex" (free) or "sip" (paid)

    @property
    def has_alpaca(self) -> bool:
        return bool(self.alpaca_api_key and self.alpaca_secret_key)

    def require_alpaca(self) -> None:
        """Fail loudly and early if Alpaca credentials are missing."""
        if not self.has_alpaca:
            raise RuntimeError(
                "Alpaca credentials missing. Set ALPACA_API_KEY and ALPACA_SECRET_KEY "
                "in your environment or .env file (copy .env.example). Free paper-trading "
                "keys: https://alpaca.markets/"
            )


def get_settings() -> Settings:
    return Settings(
        alpaca_api_key=os.getenv("ALPACA_API_KEY"),
        alpaca_secret_key=os.getenv("ALPACA_SECRET_KEY"),
        alpaca_paper=_as_bool(os.getenv("ALPACA_PAPER"), default=True),
        alpaca_data_feed=os.getenv("ALPACA_DATA_FEED", "iex"),
    )
