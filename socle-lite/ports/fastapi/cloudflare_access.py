"""Vérification du badge Cloudflare Access — port FastAPI / Starlette.

Repris À L'IDENTIQUE de la logique testée du site-base (Flask), adapté à
Starlette (l'objet `Request`). Même algorithme, mêmes garanties.

Dépendances : PyJWT[crypto]  (BotPanel les a déjà).

Utilisation (dans une route FastAPI) :

    from cloudflare_access import cf_access_email

    @app.get("/gateway")
    async def gateway(request: Request):
        email = cf_access_email(request, team=CF_TEAM, aud=CF_AUD, verify=CF_VERIFY)
        if email is None:
            ...  # pas de badge → login local / refus (selon ta config)
        else:
            ...  # authentifié : ouvre ta session pour cet e-mail

⚠️ Ne jamais faire confiance à l'en-tête `Cf-Access-Authenticated-User-Email`
seul : on vérifie le JWT `Cf-Access-Jwt-Assertion` (RS256) + `aud` + `iss`.
Et rends l'origine injoignable hors Cloudflare (tunnel / pare-feu IP Cloudflare).
"""
from __future__ import annotations

import jwt
from jwt import PyJWKClient

# Cache des clients JWK, par équipe (la config peut changer).
_jwk_clients: dict[str, PyJWKClient] = {}


def _normalize_team(raw: str) -> str:
    t = (raw or "").strip().lower()
    t = t.replace("https://", "").replace("http://", "").strip("/")
    return t.replace(".cloudflareaccess.com", "")


def _get_jwk_client(team: str) -> PyJWKClient | None:
    if not team:
        return None
    client = _jwk_clients.get(team)
    if client is None:
        client = PyJWKClient(f"https://{team}.cloudflareaccess.com/cdn-cgi/access/certs")
        _jwk_clients[team] = client
    return client


def cf_access_email(request, *, team: str, aud: str, verify: bool = True) -> str | None:
    """E-mail Cloudflare vérifié pour la requête, sinon None.

    `request` : un objet Starlette/FastAPI `Request` (attributs `.headers`, `.cookies`).
    `team`    : nom de l'équipe Cloudflare (ex. « super-nono »).
    `aud`     : AUD de l'application Access.
    `verify`  : True en prod (vérifie le JWT) ; False seulement en dev local.
    """
    # Starlette : en-têtes insensibles à la casse.
    header_email = request.headers.get("cf-access-authenticated-user-email")
    if not verify:
        return header_email.strip().lower() if header_email else None

    token = (request.headers.get("cf-access-jwt-assertion")
             or request.cookies.get("CF_Authorization"))
    if not token:
        return None

    team = _normalize_team(team)
    aud = (aud or "").strip()
    client = _get_jwk_client(team)
    if client is None or not aud or not team:
        return None

    try:
        signing_key = client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token, signing_key.key, algorithms=["RS256"],
            audience=aud, issuer=f"https://{team}.cloudflareaccess.com",
        )
    except Exception:  # signature invalide, expiré, aud/iss faux…
        return None

    email = (claims.get("email") or "").strip().lower()
    return email or None
