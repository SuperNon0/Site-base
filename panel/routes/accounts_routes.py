"""Gestion des comptes (Paramètres → Comptes) + impersonation.

Conforme à docs/authentification-v2.md §5 (gestion), §6 (voir en tant que) et
§8 (endpoints). Les formulaires HTML n'acceptant que GET/POST, toutes les
actions sont en POST (la spec §8 les décrit en verbes REST — même effet).
"""

from __future__ import annotations

import time

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   session, url_for)

from ..auth import (current_compte, get_compte, is_super_admin,
                    login_required, super_admin_required)
from ..db import audit, get_db
from ..notify import notify
from ..utils import fmt_dt

bp = Blueprint("accounts", __name__)


def _row_to_view(row) -> dict:
    d = dict(row)
    d["cree_fmt"] = fmt_dt(row["cree"], with_time=False)
    d["derniere_cnx_fmt"] = fmt_dt(row["derniere_cnx"])
    d["bloque_fmt"] = fmt_dt(row["bloque"], with_time=False)
    return d


@bp.route("/parametres/comptes")
@super_admin_required
def comptes():
    db = get_db()
    pending = [_row_to_view(r) for r in db.execute(
        "SELECT * FROM comptes WHERE etat = 'pending' ORDER BY cree DESC").fetchall()]
    membres = [_row_to_view(r) for r in db.execute(
        "SELECT * FROM comptes WHERE etat IN ('actif', 'bloque') "
        "ORDER BY (role = 'super_admin') DESC, email").fetchall()]
    # id du super-admin réel (même en impersonation) pour marquer « toi ».
    moi_id = session.get("impersonator_id") or session.get("compte_id")
    return render_template("comptes.html", pending=pending, membres=membres, moi_id=moi_id)


def _acteur() -> str:
    c = get_compte(session.get("impersonator_id") or session.get("compte_id"))
    return (c["email"] if c and c["email"] else "super_admin")


@bp.route("/api/comptes/<int:compte_id>/valider", methods=["POST"])
@super_admin_required
def valider(compte_id: int):
    db = get_db()
    c = get_compte(compte_id)
    if c and c["etat"] == "pending":
        db.execute("UPDATE comptes SET etat = 'actif', valide = ? WHERE id = ?",
                   (int(time.time()), compte_id))
        db.commit()
        audit("valider", _acteur(), c["email"])
        notify(current_app.config["NOTIFY_SLUG_ACCESS_VALIDATED"], email=c["email"])
        flash(f"{c['email']} a été validé.", "success")
    return redirect(url_for("accounts.comptes"))


@bp.route("/api/comptes/<int:compte_id>/refuser", methods=["POST"])
@super_admin_required
def refuser(compte_id: int):
    db = get_db()
    c = get_compte(compte_id)
    if c and c["etat"] == "pending":
        db.execute("UPDATE comptes SET etat = 'refused' WHERE id = ?", (compte_id,))
        db.commit()
        audit("refuser", _acteur(), c["email"])
        flash(f"Demande de {c['email']} refusée.", "info")
    return redirect(url_for("accounts.comptes"))


@bp.route("/api/comptes/<int:compte_id>/bloquer", methods=["POST"])
@super_admin_required
def bloquer(compte_id: int):
    db = get_db()
    c = get_compte(compte_id)
    if c and c["role"] != "super_admin" and c["etat"] == "actif":
        db.execute("UPDATE comptes SET etat = 'bloque', bloque = ? WHERE id = ?",
                   (int(time.time()), compte_id))
        db.commit()
        audit("bloquer", _acteur(), c["email"])
        notify(current_app.config["NOTIFY_SLUG_ACCESS_BLOCKED"], email=c["email"])
        flash(f"{c['email']} a été bloqué.", "info")
    return redirect(url_for("accounts.comptes"))


@bp.route("/api/comptes/<int:compte_id>/debloquer", methods=["POST"])
@super_admin_required
def debloquer(compte_id: int):
    db = get_db()
    c = get_compte(compte_id)
    if c and c["etat"] == "bloque":
        db.execute("UPDATE comptes SET etat = 'actif', bloque = NULL WHERE id = ?",
                   (compte_id,))
        db.commit()
        audit("debloquer", _acteur(), c["email"])
        flash(f"{c['email']} a été débloqué.", "success")
    return redirect(url_for("accounts.comptes"))


@bp.route("/api/comptes/<int:compte_id>/supprimer", methods=["POST"])
@super_admin_required
def supprimer(compte_id: int):
    db = get_db()
    c = get_compte(compte_id)
    if c is None:
        return redirect(url_for("accounts.comptes"))
    # Le dernier super-admin est indestructible (spec §9.3).
    if c["role"] == "super_admin":
        flash("Impossible de supprimer un super-admin.", "error")
        return redirect(url_for("accounts.comptes"))
    db.execute("DELETE FROM comptes WHERE id = ?", (compte_id,))
    db.commit()
    audit("supprimer", _acteur(), c["email"])
    flash(f"{c['email']} a été supprimé.", "info")
    return redirect(url_for("accounts.comptes"))


# ── Impersonation « voir en tant que » (spec §6) ────────────────────────────
@bp.route("/api/comptes/<int:compte_id>/impersonate", methods=["POST"])
@super_admin_required
def impersonate(compte_id: int):
    # Pas d'impersonation en cascade, ni d'un autre super-admin (spec §6).
    if session.get("impersonator_id"):
        flash("Déjà en impersonation.", "error")
        return redirect(url_for("accounts.comptes"))
    cible = get_compte(compte_id)
    if cible is None or cible["role"] == "super_admin" or cible["etat"] != "actif":
        flash("Compte non impersonnable.", "error")
        return redirect(url_for("accounts.comptes"))

    session["impersonator_id"] = session["compte_id"]
    session["compte_id"] = compte_id
    audit("impersonate_start", _acteur(), cible["email"])
    flash(f"Tu consultes maintenant le compte de {cible['email']}.", "info")
    return redirect(url_for("main.dashboard"))


@bp.route("/api/impersonate/stop", methods=["POST"])
@login_required
def impersonate_stop():
    real_id = session.pop("impersonator_id", None)
    if real_id:
        cible = get_compte(session.get("compte_id"))
        session["compte_id"] = real_id
        audit("impersonate_stop", _acteur(), cible["email"] if cible else None)
    return redirect(url_for("main.dashboard"))
