"""Écran applicatif de démonstration (à remplacer par ton projet)."""

from __future__ import annotations

from flask import Blueprint, current_app, render_template

from ..auth import cf_access_email, current_compte, is_super_admin, login_required

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def dashboard():
    return render_template(
        "dashboard.html",
        compte=current_compte(),
        is_super_admin=is_super_admin(),
        cf_email=cf_access_email(),
        botpanel_url=current_app.config.get("BOTPANEL_URL"),
    )
