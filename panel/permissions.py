"""Permissions (capabilities) configurables par site.

Chaque fonctionnalité sensible est une *capability* avec un niveau requis, choisi
à la création du site (voir docs/permissions.md et le contrat CLAUDE.md) :

    off          → personne (la fonctionnalité est désactivée sur ce site)
    membre       → tout compte actif (membre ou super-admin)
    super_admin  → super-admin uniquement

Le niveau est lu depuis la config `CAP_<CLE>` (donc `.env`). Cas particulier :
`account_management` pilote aussi le **modèle d'accès** du site :
    - niveau ≠ off  → site « géré » (hub) : flux demande → validation → actif,
                       blocage, suppression, rôles.
    - niveau = off  → site « perso » : l'utilisateur (déjà filtré par Cloudflare)
                       est créé automatiquement en `actif` à sa 1re visite ; pas
                       de validation ni de blocage en local (géré au hub).
"""

from __future__ import annotations

import functools

from flask import current_app, flash, jsonify, redirect, request, url_for

from .auth import current_compte, is_super_admin

LEVELS = ("off", "membre", "super_admin")

# clé → (libellé, description, niveau par défaut)
CAPABILITIES: dict[str, tuple[str, str, str]] = {
    "account_management": (
        "Gestion des comptes",
        "Demandes d'accès, validation, refus, blocage, suppression, rôles. "
        "Désactivée = site « perso » (utilisateurs auto-créés en actif, gestion au hub).",
        "super_admin",
    ),
    "profiles": (
        "Profils & « se mettre à leur place »",
        "Voir les profils du site et les impersonner (voir/éditer leurs données).",
        "super_admin",
    ),
    "admin_password": (
        "Mot de passe administrateur",
        "Changer le mot de passe admin dans les Paramètres.",
        "super_admin",
    ),
    "site_update": (
        "Mise à jour du site",
        "Bouton « Mettre à jour » (git + pip + redémarrage) et /api/system/*.",
        "super_admin",
    ),
}


def capability_level(key: str) -> str:
    """Niveau configuré pour une capability (off | membre | super_admin)."""
    default = CAPABILITIES[key][2]
    val = (current_app.config.get(f"CAP_{key.upper()}") or default).strip().lower()
    return val if val in LEVELS else default


def access_managed() -> bool:
    """True si le site gère les comptes (hub) ; False = site perso (auto-actif)."""
    return capability_level("account_management") != "off"


def has_capability(key: str) -> bool:
    """L'utilisateur courant a-t-il le droit `key` ?"""
    level = capability_level(key)
    if level == "off":
        return False
    if level == "super_admin":
        return is_super_admin()
    # 'membre' : tout compte actif (le super-admin l'est aussi)
    if is_super_admin():
        return True
    c = current_compte()
    return bool(c and c["etat"] == "actif")


def any_admin_capability() -> bool:
    """Vrai si l'utilisateur a au moins une capability (→ accès aux Paramètres)."""
    return any(has_capability(k) for k in CAPABILITIES)


def require_capability(key: str):
    """Décorateur : exige la capability `key`. 403 JSON sur /api/*, sinon redirige."""
    def decorator(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            if current_compte() is None:
                if request.path.startswith("/api/"):
                    return jsonify({"ok": False, "error": "Non authentifié."}), 401
                return redirect(url_for("auth.gateway"))
            if not has_capability(key):
                if request.path.startswith("/api/"):
                    return jsonify({"ok": False, "error": "Action non autorisée."}), 403
                flash("Action non autorisée sur ce site.", "error")
                return redirect(url_for("main.dashboard"))
            return view(*args, **kwargs)

        return wrapped

    return decorator
