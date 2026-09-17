"""Écran(s) de ton outil — À REMPLACER par ton contenu.

Tout est protégé par `login_required` : l'utilisateur est déjà authentifié
(Cloudflare ou secours local) au moment d'arriver ici.
"""
from __future__ import annotations

from flask import Blueprint, render_template, session

from .auth import login_required

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def home():
    return render_template("home.html", email=session.get("email"))
