"""Écran de configuration au premier lancement.

Tant que la config initiale n'est pas validée (`app_settings.setup_done != '1'`),
toute visite est redirigée vers `/setup`. Une fois terminé, l'écran disparaît
pour toujours. Il fixe : mot de passe admin (+ e-mail Google), Cloudflare
(équipe/AUD/vérif) et l'URL BotPanel.

⚠️ Cet écran est ouvert (pas d'auth) UNIQUEMENT tant que la config n'est pas faite
— c'est le premier lancement. Garde l'origine sur ton LAN / derrière Cloudflare
pendant l'installation.
"""

from __future__ import annotations

import time

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, url_for)
from werkzeug.security import generate_password_hash

from ..db import audit, get_db
from ..settings import (cf_config, get_setting, is_setup_done, normalize_team,
                        set_setting)

bp = Blueprint("setup", __name__)
MIN_MDP = 8


@bp.route("/setup", methods=["GET"])
def setup():
    if is_setup_done():
        return redirect(url_for("auth.gateway"))
    return render_template(
        "setup.html",
        email=current_app.config.get("SUPERADMIN_EMAIL", ""),
        cf=cf_config(),
        botpanel=(get_setting("botpanel_url") or current_app.config.get("BOTPANEL_URL", "")),
    )


@bp.route("/setup", methods=["POST"])
def setup_post():
    if is_setup_done():
        return redirect(url_for("auth.gateway"))

    db = get_db()
    pwd = request.form.get("password", "")
    confirm = request.form.get("confirm", "")
    email = (request.form.get("email") or "").strip().lower() or None

    if len(pwd) < MIN_MDP:
        flash(f"Mot de passe : minimum {MIN_MDP} caractères.", "error")
        return redirect(url_for("setup.setup"))
    if pwd != confirm:
        flash("La confirmation du mot de passe ne correspond pas.", "error")
        return redirect(url_for("setup.setup"))

    now = int(time.time())
    h = generate_password_hash(pwd)
    row = (db.execute("SELECT id FROM comptes WHERE role = 'super_admin' AND mdp_hash IS NOT NULL "
                      "ORDER BY id LIMIT 1").fetchone()
           or db.execute("SELECT id FROM comptes WHERE role = 'super_admin' ORDER BY id LIMIT 1").fetchone())

    if email:  # refuse un e-mail déjà pris par un AUTRE compte
        taken = db.execute("SELECT id FROM comptes WHERE email = ?", (email,)).fetchone()
        if taken is not None and (row is None or taken["id"] != row["id"]):
            if row is None:  # on promeut ce compte comme admin de base
                db.execute("UPDATE comptes SET role='super_admin', etat='actif', mdp_hash=?, "
                           "valide=COALESCE(valide,?) WHERE id=?", (h, now, taken["id"]))
                db.commit()
                _save_services()
                set_setting("setup_done", "1")
                audit("setup_done", acteur=email)
                flash("Configuration enregistrée. Connecte-toi.", "success")
                return redirect(url_for("auth.gateway"))
            flash("Cet e-mail est déjà utilisé par un autre compte.", "error")
            return redirect(url_for("setup.setup"))

    if row is None:
        db.execute("INSERT INTO comptes (email, role, etat, mdp_hash, cree, valide) "
                   "VALUES (?, 'super_admin', 'actif', ?, ?, ?)", (email, h, now, now))
    else:
        db.execute("UPDATE comptes SET mdp_hash = ?, email = COALESCE(?, email), etat = 'actif' "
                   "WHERE id = ?", (h, email, row["id"]))
    db.commit()

    _save_services()
    set_setting("setup_done", "1")
    audit("setup_done", acteur=email or "admin")
    flash("Configuration enregistrée. Connecte-toi.", "success")
    return redirect(url_for("auth.gateway"))


def _save_services() -> None:
    """Enregistre Cloudflare + BotPanel depuis le formulaire de setup."""
    set_setting("cf_team", normalize_team(request.form.get("team", "")))
    set_setting("cf_aud", (request.form.get("aud", "") or "").strip())
    set_setting("cf_verify", "1" if request.form.get("verify") else "0")
    set_setting("botpanel_url", (request.form.get("botpanel", "") or "").strip())
