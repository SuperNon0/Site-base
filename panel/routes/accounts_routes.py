"""Gestion des comptes (Paramètres → Comptes) + impersonation.

Conforme à docs/authentification-v2.md §5 (gestion), §6 (voir en tant que) et
§8 (endpoints). Les formulaires HTML n'acceptant que GET/POST, toutes les
actions sont en POST (la spec §8 les décrit en verbes REST — même effet).
"""

from __future__ import annotations

import time

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from ..auth import (current_compte, get_compte, is_base_admin, is_super_admin,
                    login_required, super_admin_required)
from ..db import audit, get_db
from ..notify import notify
from ..permissions import (any_admin_capability, has_capability,
                           require_capability)
from ..utils import fmt_dt

bp = Blueprint("accounts", __name__)

MIN_MDP_LEN = 8


def _row_to_view(row) -> dict:
    d = dict(row)
    d["cree_fmt"] = fmt_dt(row["cree"], with_time=False)
    d["derniere_cnx_fmt"] = fmt_dt(row["derniere_cnx"])
    d["bloque_fmt"] = fmt_dt(row["bloque"], with_time=False)
    return d


@bp.route("/parametres/comptes")
@login_required
def comptes():
    """Écran comptes/profils, adapté aux permissions du site.

    - `account_management` : gestion complète (demandes, valider, bloquer…).
    - `profiles` seul (site perso) : simple liste de profils + impersonation.
    """
    can_manage = has_capability("account_management")
    can_impersonate = has_capability("profiles")
    if not (can_manage or can_impersonate):
        flash("Action non autorisée sur ce site.", "error")
        return redirect(url_for("main.dashboard"))

    db = get_db()
    pending = []
    if can_manage:
        pending = [_row_to_view(r) for r in db.execute(
            "SELECT * FROM comptes WHERE etat = 'pending' ORDER BY cree DESC").fetchall()]
    membres = [_row_to_view(r) for r in db.execute(
        "SELECT * FROM comptes WHERE etat IN ('actif', 'bloque') "
        "ORDER BY (role = 'super_admin') DESC, email").fetchall()]
    moi_id = session.get("impersonator_id") or session.get("compte_id")
    return render_template("comptes.html", pending=pending, membres=membres,
                           moi_id=moi_id, can_manage=can_manage,
                           can_impersonate=can_impersonate)


def _acteur() -> str:
    c = get_compte(session.get("impersonator_id") or session.get("compte_id"))
    return (c["email"] if c and c["email"] else "super_admin")


# ── Paramètres : mot de passe administrateur ────────────────────────────────
@bp.route("/parametres")
@login_required
def parametres():
    # Accessible avec au moins une permission d'admin, ou pour le compte de base.
    if not (any_admin_capability() or is_base_admin()):
        flash("Action non autorisée sur ce site.", "error")
        return redirect(url_for("main.dashboard"))
    # Compte super-admin réel (jamais l'identité impersonnée).
    moi = get_compte(session.get("impersonator_id") or session.get("compte_id"))
    # Liste des super-admins « e-mail » (gérables par le compte de base).
    superadmins = []
    if is_base_admin():
        superadmins = [dict(r) for r in get_db().execute(
            "SELECT id, email, mdp_hash FROM comptes WHERE role = 'super_admin' "
            "ORDER BY (mdp_hash IS NOT NULL) DESC, email").fetchall()]
    # Cloudflare / Accès + diagnostic : réservés au super-admin.
    cf = diag = None
    if is_super_admin():
        from ..settings import cf_config
        from ..auth import cf_diagnostic
        cf = cf_config()
        diag = cf_diagnostic()
    return render_template(
        "parametres.html",
        has_password=bool(moi and moi["mdp_hash"]),
        impersonating=bool(session.get("impersonator_id")),
        superadmins=superadmins,
        moi_id=moi["id"] if moi else None,
        mon_email=moi["email"] if moi else None,
        cf=cf, diag=diag,
    )


@bp.route("/parametres/mon-email", methods=["POST"])
@login_required
def mon_email():
    """Rattache/change l'e-mail Google du compte de base (UI). Base admin uniquement.

    En cas de conflit (un autre compte a déjà l'e-mail), on refuse et on invite à
    supprimer d'abord ce compte — la fusion automatique est réservée à la console
    (deploy/set_email.sh).
    """
    if not is_base_admin():
        flash("Réservé au compte administrateur de base.", "error")
        return redirect(url_for("accounts.parametres"))
    db = get_db()
    base = get_compte(session.get("impersonator_id") or session.get("compte_id"))
    email = (request.form.get("email") or "").strip().lower()

    if not email:  # champ vide → détacher
        db.execute("UPDATE comptes SET email = NULL WHERE id = ?", (base["id"],))
        db.commit()
        audit("set_email_clear", _acteur())
        flash("E-mail détaché de ton compte.", "info")
        return redirect(url_for("accounts.parametres"))
    if "@" not in email:
        flash("E-mail invalide.", "error")
        return redirect(url_for("accounts.parametres"))

    other = db.execute("SELECT id FROM comptes WHERE email = ?", (email,)).fetchone()
    if other is not None and other["id"] != base["id"]:
        flash("Un autre compte utilise déjà cet e-mail. Supprime-le d'abord, ou "
              "fusionne en console : deploy/set_email.sh " + email, "error")
        return redirect(url_for("accounts.parametres"))

    db.execute("UPDATE comptes SET email = ? WHERE id = ?", (email, base["id"]))
    db.commit()
    audit("set_email", _acteur(), email)
    flash("E-mail Google enregistré.", "success")
    return redirect(url_for("accounts.parametres"))


@bp.route("/api/cf-test", methods=["POST"])
@login_required
def cf_test():
    """Teste en direct la connexion Cloudflare pour les valeurs saisies (bouton Tester)."""
    from flask import jsonify
    if not is_super_admin():
        return jsonify({"error": "Réservé au super-admin."}), 403
    from ..auth import cf_diagnostic
    from ..settings import normalize_team
    data = request.get_json(silent=True) or {}
    team = normalize_team(data.get("team", ""))
    aud = (data.get("aud", "") or "").strip()
    return jsonify(cf_diagnostic(team=team, aud=aud))


@bp.route("/parametres/cloudflare", methods=["POST"])
@login_required
def cloudflare_settings():
    """Enregistre la config Cloudflare (équipe/AUD/vérif). Super-admin uniquement."""
    if not is_super_admin():
        flash("Réservé au super-admin.", "error")
        return redirect(url_for("accounts.parametres"))
    from ..settings import normalize_team, set_setting
    set_setting("cf_team", normalize_team(request.form.get("team", "")))
    set_setting("cf_aud", (request.form.get("aud", "") or "").strip())
    set_setting("cf_verify", "1" if request.form.get("verify") else "0")
    audit("cf_settings", _acteur())
    flash("Configuration Cloudflare enregistrée.", "success")
    return redirect(url_for("accounts.parametres"))


@bp.route("/parametres/super-admin/ajouter", methods=["POST"])
@login_required
def ajouter_superadmin():
    """Désigne un e-mail comme super-admin. RÉSERVÉ au compte administrateur de base."""
    if not is_base_admin():
        flash("Seul le compte administrateur peut ajouter un super-admin.", "error")
        return redirect(url_for("accounts.parametres"))
    email = (request.form.get("email") or "").strip().lower()
    if not email or "@" not in email:
        flash("E-mail invalide.", "error")
        return redirect(url_for("accounts.parametres"))

    db = get_db()
    now = int(time.time())
    c = db.execute("SELECT * FROM comptes WHERE email = ?", (email,)).fetchone()
    if c is None:
        db.execute("INSERT INTO comptes (email, role, etat, cree, valide) "
                   "VALUES (?, 'super_admin', 'actif', ?, ?)", (email, now, now))
    else:
        db.execute("UPDATE comptes SET role = 'super_admin', etat = 'actif', "
                   "valide = COALESCE(valide, ?) WHERE id = ?", (now, c["id"]))
    db.commit()
    audit("ajouter_superadmin", _acteur(), email)
    flash(f"{email} est désormais super-admin.", "success")
    return redirect(url_for("accounts.parametres"))


@bp.route("/parametres/super-admin/<int:compte_id>/retirer", methods=["POST"])
@login_required
def retirer_superadmin(compte_id: int):
    """Retire le rôle super-admin d'un compte « e-mail ». RÉSERVÉ au compte de base."""
    if not is_base_admin():
        flash("Seul le compte administrateur peut retirer un super-admin.", "error")
        return redirect(url_for("accounts.parametres"))
    db = get_db()
    c = get_compte(compte_id)
    if c is None or c["role"] != "super_admin":
        return redirect(url_for("accounts.parametres"))
    if c["mdp_hash"]:
        flash("Le compte administrateur de base n'est pas modifiable ici.", "error")
        return redirect(url_for("accounts.parametres"))
    # Ne jamais retirer le dernier super-admin.
    n = db.execute("SELECT COUNT(*) FROM comptes WHERE role = 'super_admin'").fetchone()[0]
    if n <= 1:
        flash("Impossible : c'est le dernier super-admin.", "error")
        return redirect(url_for("accounts.parametres"))
    db.execute("UPDATE comptes SET role = 'membre' WHERE id = ?", (compte_id,))
    db.commit()
    audit("retirer_superadmin", _acteur(), c["email"])
    flash(f"{c['email']} n'est plus super-admin.", "info")
    return redirect(url_for("accounts.parametres"))


@bp.route("/parametres/mot-de-passe", methods=["POST"])
@require_capability("admin_password")
def changer_mdp():
    # Interdit pendant une impersonation (on ne change pas le mdp d'un autre).
    if session.get("impersonator_id"):
        flash("Reviens à ton compte avant de changer le mot de passe.", "error")
        return redirect(url_for("accounts.parametres"))

    db = get_db()
    moi = get_compte(session.get("compte_id"))
    actuel = request.form.get("actuel", "")
    nouveau = request.form.get("nouveau", "")
    confirme = request.form.get("confirme", "")

    # Si un mot de passe existe déjà, il faut fournir l'actuel.
    if moi["mdp_hash"] and not check_password_hash(moi["mdp_hash"], actuel):
        flash("Mot de passe actuel incorrect.", "error")
        return redirect(url_for("accounts.parametres"))
    if len(nouveau) < MIN_MDP_LEN:
        flash(f"Le nouveau mot de passe doit faire au moins {MIN_MDP_LEN} caractères.", "error")
        return redirect(url_for("accounts.parametres"))
    if nouveau != confirme:
        flash("La confirmation ne correspond pas.", "error")
        return redirect(url_for("accounts.parametres"))

    db.execute("UPDATE comptes SET mdp_hash = ? WHERE id = ?",
               (generate_password_hash(nouveau), moi["id"]))
    db.commit()
    audit("changer_mdp", _acteur())
    flash("Mot de passe administrateur mis à jour.", "success")
    return redirect(url_for("accounts.parametres"))


@bp.route("/api/comptes/<int:compte_id>/valider", methods=["POST"])
@require_capability("account_management")
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
@require_capability("account_management")
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
@require_capability("account_management")
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
@require_capability("account_management")
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
@require_capability("account_management")
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
@require_capability("profiles")
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
