"""Endpoints SSO du HUB : émettre / purger le cookie de session partagé.

Actifs uniquement quand AUTH_MODE == "hub". Un client redirige l'utilisateur
vers `{hub}/sso/login?next=<url_client>` : le hub l'authentifie via Cloudflare,
pose le cookie partagé sur le domaine parent, puis renvoie vers `next`.

Voir docs/sso-hub.md.
"""

from __future__ import annotations

from flask import (Blueprint, current_app, make_response, redirect, request,
                   session, url_for)

from ..auth import cf_access_email
from ..db import audit
from .. import sso

bp = Blueprint("sso", __name__)


def _is_hub() -> bool:
    return current_app.config.get("AUTH_MODE") == "hub"


@bp.route("/sso/login")
def sso_login():
    """Émet le cookie partagé pour l'e-mail Cloudflare vérifié, puis redirige."""
    if not _is_hub():
        return redirect(url_for("auth.gateway"))

    nxt = request.args.get("next", "")
    email = cf_access_email()
    if email is None:
        # Pas encore authentifié par Cloudflare au hub → passe par le gateway du
        # hub (Cloudflare montrera Google si besoin). On garde `next` en session.
        if nxt:
            session["sso_next"] = nxt
        return redirect(url_for("auth.gateway"))

    # Destination : `next` (validé même domaine) sinon la session courante.
    target = None
    candidate = nxt or session.pop("sso_next", "")
    if candidate and sso.is_safe_next(candidate):
        target = candidate
    resp = make_response(redirect(target or url_for("main.dashboard")))
    sso.set_cookie(resp, email)
    audit("sso_login", acteur=email)
    return resp


@bp.route("/sso/logout")
def sso_logout():
    """Purge le cookie partagé (déconnexion globale), puis redirige."""
    if not _is_hub():
        return redirect(url_for("auth.gateway"))

    nxt = request.args.get("next", "")
    target = nxt if sso.is_safe_next(nxt) else url_for("auth.gateway")
    resp = make_response(redirect(target))
    sso.clear_cookie(resp)
    session.clear()
    return resp
