"""SSO par cookie de session partagé (sous-domaines d'un même domaine).

Le **hub** authentifie l'utilisateur (via Cloudflare Access) puis émet un cookie
signé sur le **domaine parent** (`.super-nono.cc`). Chaque **client** lit ce
cookie, vérifie sa signature avec le **secret partagé** (`SSO_SECRET`) et en
déduit l'e-mail vérifié — puis applique son PROPRE contrôle d'accès (cycle de vie
des comptes + rôles), exactement comme avec l'en-tête Cloudflare en mode autonome.

Voir docs/sso-hub.md.
"""

from __future__ import annotations

import time
from urllib.parse import urlsplit

import jwt
from flask import current_app, request


def _secret() -> str:
    return current_app.config.get("SSO_SECRET") or ""


def _cookie_name() -> str:
    return current_app.config.get("SSO_COOKIE_NAME", "sso_session")


def issue_token(email: str) -> str:
    """Jeton signé (JWT HS256) portant l'e-mail vérifié + expiration."""
    now = int(time.time())
    ttl = int(current_app.config.get("SSO_TTL", 43200))
    return jwt.encode(
        {"sub": email, "iat": now, "exp": now + ttl, "iss": "hub"},
        _secret(), algorithm="HS256",
    )


def read_token() -> str | None:
    """E-mail vérifié depuis le cookie SSO de la requête courante, sinon None."""
    tok = request.cookies.get(_cookie_name())
    if not tok or not _secret():
        return None
    try:
        claims = jwt.decode(tok, _secret(), algorithms=["HS256"],
                            options={"require": ["exp"]})
    except Exception as exc:  # signature invalide, expiré…
        current_app.logger.debug("Cookie SSO rejeté : %s", exc)
        return None
    email = (claims.get("sub") or "").strip().lower()
    return email or None


def set_cookie(resp, email: str) -> None:
    resp.set_cookie(
        _cookie_name(), issue_token(email),
        max_age=int(current_app.config.get("SSO_TTL", 43200)),
        domain=(current_app.config.get("SSO_COOKIE_DOMAIN") or None),
        secure=current_app.config.get("SESSION_COOKIE_SECURE", False),
        httponly=True, samesite="Lax",
    )


def clear_cookie(resp) -> None:
    resp.delete_cookie(
        _cookie_name(),
        domain=(current_app.config.get("SSO_COOKIE_DOMAIN") or None),
    )


def is_safe_next(url: str) -> bool:
    """Vrai si `url` pointe vers un hôte du domaine autorisé (anti open-redirect).

    On n'autorise la redirection que vers un hôte se terminant par
    SSO_COOKIE_DOMAIN (ex. « .super-nono.cc »). Une URL relative est refusée ici
    (on attend une URL absolue de sous-domaine).
    """
    if not url:
        return False
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return False
    dom = (current_app.config.get("SSO_COOKIE_DOMAIN") or "").lstrip(".").lower()
    if not dom:
        return False
    host = parts.hostname.lower()
    return host == dom or host.endswith("." + dom)


def hub_login_url(next_url: str) -> str:
    """URL de login du hub à laquelle un client redirige (avec retour `next`)."""
    base = (current_app.config.get("SSO_HUB_URL") or "").rstrip("/")
    from urllib.parse import quote
    return f"{base}/sso/login?next={quote(next_url, safe='')}"
