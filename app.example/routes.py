"""Écrans du projet (exemple). Tu réutilises la base sans la modifier.

- `login_required` / `super_admin_required` viennent de la base (`panel.auth`).
- Le thème et le layout `base.html` viennent de la base : `{% extends "base.html" %}`.
- Les données par utilisateur : filtre par le compte *effectif* (impersonation
  incluse) → `current_compte()["id"]`.
"""

from __future__ import annotations

from flask import Blueprint, render_template

from panel.auth import current_compte, is_super_admin, login_required
from panel.db import get_db

bp = Blueprint("app", __name__)


@bp.route("/")
@login_required
def dashboard():
    """Écran d'accueil du projet — remplace la démo de la base."""
    compte = current_compte()
    # Exemple : compter les éléments de CE compte (données cloisonnées).
    n = get_db().execute(
        "SELECT COUNT(*) FROM exemple_items WHERE compte_id = ?", (compte["id"],)
    ).fetchone()[0]
    return render_template("dashboard.html", compte=compte,
                           is_super_admin=is_super_admin(), nb_items=n)
