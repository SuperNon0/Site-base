"""Authentification : Cloudflare Zero Trust (Access) + login local + décorateurs.

Deux couches, conformes à docs/authentification-v2.md §1 et §9 :
  - Cloudflare Access = portier e-mail (qui peut *frapper à la porte*).
  - L'application       = rôles + cycle de vie (ce qui se passe *après* la porte).

⚠️ Sécurité (spec §9.1) : ne JAMAIS faire confiance à l'en-tête
`Cf-Access-Authenticated-User-Email` si l'origine est joignable hors Cloudflare.
On vérifie donc le JWT `Cf-Access-Jwt-Assertion` contre les clés publiques de
l'équipe Cloudflare et on contrôle l'`aud`. Rends aussi l'origine injoignable
sans Cloudflare (tunnel cloudflared / pare-feu IP Cloudflare).
"""

from __future__ import annotations

import functools
import time

from flask import (current_app, flash, g, redirect, request, session, url_for)

from .db import get_db

# PyJWT est optionnel au démarrage : on n'exige la lib que si CF_VERIFY_JWT.
try:
    import jwt
    from jwt import PyJWKClient
except Exception:  # pragma: no cover
    jwt = None
    PyJWKClient = None

# Cache des clients JWK, PAR équipe (la config peut changer via l'UI).
_jwk_clients: dict[str, "PyJWKClient"] = {}


# ─────────────────────────────────────────────────────────────────────────────
# Cloudflare Access
# ─────────────────────────────────────────────────────────────────────────────
def _get_jwk_client(team: str) -> "PyJWKClient | None":
    if not team or PyJWKClient is None:
        return None
    client = _jwk_clients.get(team)
    if client is None:
        certs_url = f"https://{team}.cloudflareaccess.com/cdn-cgi/access/certs"
        client = PyJWKClient(certs_url)
        _jwk_clients[team] = client
    return client


def _cf_token() -> str | None:
    """Jeton Cloudflare : en-tête `Cf-Access-Jwt-Assertion` ou cookie `CF_Authorization`."""
    return (request.headers.get("Cf-Access-Jwt-Assertion")
            or request.cookies.get("CF_Authorization"))


def cf_access_email() -> str | None:
    """E-mail Cloudflare vérifié pour la requête courante, sinon None.

    Configuration lue via `settings.cf_config()` (UI prioritaire, puis `.env`).
    - Si `verify` (défaut) : valide le JWT (RS256) + `aud` + `iss`, renvoie
      l'e-mail du token. Un en-tête forgé sans JWT valide est ignoré.
    - Sinon : se contente de l'en-tête `Cf-Access-Authenticated-User-Email`.
    """
    from .settings import cf_config
    cfg = cf_config()
    header_email = request.headers.get("Cf-Access-Authenticated-User-Email")

    if not cfg["verify"]:
        return header_email.strip().lower() if header_email else None

    token = _cf_token()
    if not token or jwt is None:
        return None
    team, aud = cfg["team"], cfg["aud"]
    client = _get_jwk_client(team)
    if client is None or not aud or not team:
        current_app.logger.warning(
            "Vérif JWT active mais équipe/AUD Cloudflare non renseignés."
        )
        return None

    try:
        signing_key = client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token, signing_key.key, algorithms=["RS256"],
            audience=aud, issuer=f"https://{team}.cloudflareaccess.com",
        )
    except Exception as exc:  # signature invalide, expiré, aud/iss faux…
        current_app.logger.warning("JWT Cloudflare rejeté : %s", exc)
        return None

    email = (claims.get("email") or "").strip().lower()
    return email or None


def cf_diagnostic(team: str | None = None, aud: str | None = None) -> dict:
    """Diagnostic de la connexion Cloudflare (affiché dans Paramètres).

    Sans argument : teste la config enregistrée (`cf_config()`). Avec `team`/`aud`,
    teste ces valeurs **en direct** (bouton « Tester », avant enregistrement).

    Renvoie : team, aud, verify, header_email, has_token, jwt_status
    (« non testé » | « OK ✓ » | « échec ✗ »), jwt_email, jwt_error.
    """
    from .settings import cf_config
    cfg = cf_config()
    if team is not None:
        cfg = {"team": team, "aud": (aud if aud is not None else cfg["aud"]), "verify": cfg["verify"]}
    header_email = request.headers.get("Cf-Access-Authenticated-User-Email")
    token = _cf_token()
    d = {
        "team": cfg["team"], "aud": cfg["aud"], "verify": cfg["verify"],
        "header_email": header_email, "has_token": bool(token),
        "jwt_status": "non testé", "jwt_email": None, "jwt_error": None,
    }
    if not token:
        d["jwt_error"] = "Aucun jeton Cloudflare reçu (l'origine n'est peut-être pas derrière Access)."
        return d
    if not cfg["team"] or not cfg["aud"]:
        d["jwt_error"] = "Équipe et/ou AUD non renseignés."
        return d
    if jwt is None:
        d["jwt_error"] = "PyJWT indisponible."
        return d
    try:
        client = _get_jwk_client(cfg["team"])
        signing_key = client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token, signing_key.key, algorithms=["RS256"],
            audience=cfg["aud"], issuer=f"https://{cfg['team']}.cloudflareaccess.com",
        )
        d["jwt_status"] = "OK ✓"
        d["jwt_email"] = (claims.get("email") or "").strip().lower() or None
    except Exception as exc:
        d["jwt_status"] = "échec ✗"
        d["jwt_error"] = str(exc)
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Comptes / session
# ─────────────────────────────────────────────────────────────────────────────
def home_url() -> str:
    """URL de l'accueil, quel que soit le fournisseur (surcouche `app/` ou démo base).

    Cherche l'endpoint qui sert « / » et construit son URL. Découple la base de
    l'écran d'accueil : la surcouche peut fournir le sien sans casser les
    redirections de la base.
    """
    for rule in current_app.url_map.iter_rules():
        if rule.rule == "/" and "GET" in (rule.methods or set()):
            try:
                return url_for(rule.endpoint)
            except Exception:
                break
    return "/"


def get_compte(compte_id: int):
    if compte_id is None:
        return None
    return get_db().execute("SELECT * FROM comptes WHERE id = ?", (compte_id,)).fetchone()


def current_compte():
    """Compte *effectif* (celui impersonné le cas échéant), attaché à g."""
    if "compte" not in g:
        g.compte = get_compte(session.get("compte_id"))
    return g.compte


def is_super_admin() -> bool:
    # Le rôle réel est celui de l'impersonateur s'il y en a un, sinon du compte.
    if session.get("impersonator_id"):
        imp = get_compte(session["impersonator_id"])
        return bool(imp and imp["role"] == "super_admin")
    c = current_compte()
    return bool(c and c["role"] == "super_admin")


def is_base_admin() -> bool:
    """« Compte administrateur de base » : super-admin AVEC login local (mot de passe).

    C'est le compte racine (amorcé par SUPERADMIN_PASSWORD). Lui seul peut désigner
    d'autres super-admins ; un super-admin « e-mail » (mdp_hash NULL) ne le peut pas.
    """
    real_id = session.get("impersonator_id") or session.get("compte_id")
    c = get_compte(real_id)
    return bool(c and c["role"] == "super_admin" and c["mdp_hash"])


def login_compte(compte_row) -> None:
    """Ouvre la session pour un compte actif et note la dernière connexion."""
    session.clear()
    session["compte_id"] = compte_row["id"]
    session["role"] = compte_row["role"]
    get_db().execute(
        "UPDATE comptes SET derniere_cnx = ? WHERE id = ?",
        (int(time.time()), compte_row["id"]),
    )
    get_db().commit()


# ─────────────────────────────────────────────────────────────────────────────
# Décorateurs
# ─────────────────────────────────────────────────────────────────────────────
def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        c = current_compte()
        if c is None or c["etat"] != "actif":
            return redirect(url_for("auth.gateway"))
        return view(*args, **kwargs)

    return wrapped


def super_admin_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if current_compte() is None:
            return redirect(url_for("auth.gateway"))
        if not is_super_admin():
            flash("Réservé au super-admin.", "error")
            return redirect(home_url())
        return view(*args, **kwargs)

    return wrapped
