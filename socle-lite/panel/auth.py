"""Authentification du socle-lite : Cloudflare Access + secours local, sans compte.

Deux entrées possibles, un seul « statut » : authentifié ou refusé.
  - Cloudflare Access : e-mail vérifié par JWT (RS256 + aud + iss). C'est le portier.
  - Secours local (LAN) : un mot de passe, utile si Cloudflare est indisponible.

⚠️ Le code de vérification du JWT est repris À L'IDENTIQUE du site-base (testé).
Ne jamais faire confiance à l'en-tête `Cf-Access-Authenticated-User-Email` seul :
on vérifie le jeton `Cf-Access-Jwt-Assertion` + l'`aud`, et on rend l'origine
injoignable hors Cloudflare (tunnel cloudflared / pare-feu IP Cloudflare).
"""
from __future__ import annotations

import functools
import hmac
import time

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, session, url_for)

try:
    import jwt
    from jwt import PyJWKClient
except Exception:  # PyJWT optionnel tant que CF_VERIFY_JWT n'est pas actif
    jwt = None
    PyJWKClient = None

bp = Blueprint("auth", __name__)
_jwk_clients: dict[str, "PyJWKClient"] = {}


# ── Cloudflare Access ────────────────────────────────────────────────────────
def _normalize_team(raw: str) -> str:
    t = (raw or "").strip().lower()
    t = t.replace("https://", "").replace("http://", "").strip("/")
    return t.replace(".cloudflareaccess.com", "")


def _cf_config() -> dict:
    c = current_app.config
    return {
        "team": _normalize_team(c["CF_ACCESS_TEAM_DOMAIN"]),
        "aud": (c["CF_ACCESS_AUD"] or "").strip(),
        "verify": bool(c["CF_VERIFY_JWT"]),
    }


def _get_jwk_client(team: str):
    if not team or PyJWKClient is None:
        return None
    client = _jwk_clients.get(team)
    if client is None:
        client = PyJWKClient(f"https://{team}.cloudflareaccess.com/cdn-cgi/access/certs")
        _jwk_clients[team] = client
    return client


def _cf_token() -> str | None:
    return (request.headers.get("Cf-Access-Jwt-Assertion")
            or request.cookies.get("CF_Authorization"))


def cf_access_email() -> str | None:
    """E-mail Cloudflare vérifié pour la requête, sinon None (repris du site-base)."""
    cfg = _cf_config()
    header_email = request.headers.get("Cf-Access-Authenticated-User-Email")
    if not cfg["verify"]:
        return header_email.strip().lower() if header_email else None
    token = _cf_token()
    if not token or jwt is None:
        return None
    team, aud = cfg["team"], cfg["aud"]
    client = _get_jwk_client(team)
    if client is None or not aud or not team:
        current_app.logger.warning("Vérif JWT active mais équipe/AUD non renseignés.")
        return None
    try:
        signing_key = client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token, signing_key.key, algorithms=["RS256"],
            audience=aud, issuer=f"https://{team}.cloudflareaccess.com",
        )
    except Exception as exc:
        current_app.logger.warning("JWT Cloudflare rejeté : %s", exc)
        return None
    email = (claims.get("email") or "").strip().lower()
    return email or None


# ── Décision d'accès (un seul statut : autorisé / refusé) ────────────────────
def _email_autorise(email: str) -> bool:
    allowed = current_app.config["ALLOWED_EMAILS"]
    return (not allowed) or (email in allowed)  # liste vide → on fait confiance à Cloudflare


def _local_login_possible() -> bool:
    return bool(current_app.config["ALLOW_LOCAL_LOGIN"] and current_app.config["ADMIN_PASSWORD"])


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("auth"):
            return redirect(url_for("auth.gateway"))
        return view(*args, **kwargs)
    return wrapped


@bp.route("/gateway")
def gateway():
    """Point d'entrée : Cloudflare d'abord, secours local sinon."""
    email = cf_access_email()
    if email is not None:
        if not _email_autorise(email):
            return render_template("bloque.html", email=email), 403
        session["auth"] = True
        session["email"] = email
        return redirect(url_for("main.home"))
    # Pas d'e-mail Cloudflare → accès local (LAN)
    if not _local_login_possible():
        return render_template("bloque.html", email="—"), 403
    return render_template("login.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return redirect(url_for("auth.gateway"))
    if cf_access_email() is not None:      # déjà authentifié par Cloudflare
        return redirect(url_for("auth.gateway"))
    if not _local_login_possible():        # login local désactivé → refus (même en POST)
        return render_template("bloque.html", email="—"), 403
    time.sleep(1)  # anti-force brute
    password = request.form.get("password", "")
    if hmac.compare_digest(password, current_app.config["ADMIN_PASSWORD"]):
        session["auth"] = True
        session["email"] = "admin (local)"
        return redirect(url_for("main.home"))
    flash("Mot de passe incorrect.", "error")
    return redirect(url_for("auth.gateway"))


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.gateway"))
