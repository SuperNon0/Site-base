"""Config du socle-lite (depuis .env). Aucune base de données, aucun compte."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Marque
    BRAND_PREFIX = os.getenv("BRAND_PREFIX", "Mon")
    BRAND_SUFFIX = os.getenv("BRAND_SUFFIX", "Outil")
    BRAND_BADGE = os.getenv("BRAND_BADGE", "app")

    # Cloudflare Access (le portier)
    CF_ACCESS_TEAM_DOMAIN = os.getenv("CF_ACCESS_TEAM_DOMAIN", "")
    CF_ACCESS_AUD = os.getenv("CF_ACCESS_AUD", "")
    CF_VERIFY_JWT = _bool("CF_VERIFY_JWT", True)

    # Secours local (LAN) : mot de passe. Vide OU ALLOW_LOCAL_LOGIN=false → pas de login local.
    ALLOW_LOCAL_LOGIN = _bool("ALLOW_LOCAL_LOGIN", True)
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

    # Optionnel : restreindre AUSSI côté appli (sinon on fait confiance à la liste
    # d'e-mails de Cloudflare Access). Ex : ALLOWED_EMAILS=toi@gmail.com,autre@gmail.com
    ALLOWED_EMAILS = [
        e.strip().lower() for e in os.getenv("ALLOWED_EMAILS", "").split(",") if e.strip()
    ]
