"""Rattache / retire l'e-mail Google du compte administrateur de base.

    python -m panel.set_email ton.email@gmail.com   # rattache
    python -m panel.set_email --clear                # détache

Si un AUTRE compte possède déjà cet e-mail, il est **fusionné** dans le compte de
base : toutes les données par utilisateur (n'importe quelle table ayant une colonne
`compte_id`) sont réattribuées au compte de base, puis le doublon est supprimé —
**sans rien perdre**. C'est la version « console » (l'UI, elle, demande de
supprimer d'abord le compte en conflit).

Wrappé par deploy/set_email.sh en déploiement.
"""

from __future__ import annotations

import sqlite3
import sys

from . import create_app
from .db import audit, get_db


def _base_account(db: sqlite3.Connection):
    """Le compte administrateur de base : super-admin avec login local, sinon le 1er."""
    row = db.execute(
        "SELECT * FROM comptes WHERE role = 'super_admin' AND mdp_hash IS NOT NULL "
        "ORDER BY id LIMIT 1"
    ).fetchone()
    if row is None:
        row = db.execute(
            "SELECT * FROM comptes WHERE role = 'super_admin' ORDER BY id LIMIT 1"
        ).fetchone()
    return row


def _tables_with_compte_id(db: sqlite3.Connection) -> list[str]:
    """Tables métier référençant un compte (colonne `compte_id`), hors `comptes`."""
    out = []
    for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall():
        if name in ("comptes", "app_settings", "audit", "sqlite_sequence"):
            continue
        cols = [c[1] for c in db.execute(f"PRAGMA table_info({name})").fetchall()]
        if "compte_id" in cols:
            out.append(name)
    return out


def set_email(email: str | None) -> int:
    app = create_app()
    with app.app_context():
        db = get_db()
        base = _base_account(db)
        if base is None:
            print("✗ Aucun compte super-admin.")
            return 1

        # Détacher
        if email is None:
            db.execute("UPDATE comptes SET email = NULL WHERE id = ?", (base["id"],))
            db.commit()
            audit("set_email_clear", acteur="cli")
            print("✓ E-mail détaché du compte de base.")
            return 0

        email = email.strip().lower()
        other = db.execute("SELECT * FROM comptes WHERE email = ?", (email,)).fetchone()

        if other is not None and other["id"] != base["id"]:
            # Fusion : réattribue les données du doublon au compte de base.
            reassigned = []
            for t in _tables_with_compte_id(db):
                cur = db.execute(f"UPDATE {t} SET compte_id = ? WHERE compte_id = ?",
                                 (base["id"], other["id"]))
                if cur.rowcount:
                    reassigned.append(f"{t}:{cur.rowcount}")
            db.execute("DELETE FROM comptes WHERE id = ?", (other["id"],))
            audit("merge_compte", acteur="cli", cible=email,
                  detail=f"{other['id']}→{base['id']} " + " ".join(reassigned))
            print(f"↪ Doublon fusionné (réattribué : {', '.join(reassigned) or 'rien'}).")

        db.execute("UPDATE comptes SET email = ?, etat = 'actif' WHERE id = ?", (email, base["id"]))
        db.commit()
        audit("set_email", acteur="cli", cible=email)
        print(f"✓ E-mail {email} rattaché au compte de base.")
        return 0


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--clear":
        sys.exit(set_email(None))
    if not args or "@" not in args[0]:
        print("Usage : python -m panel.set_email <email> | --clear")
        sys.exit(1)
    sys.exit(set_email(args[0]))


if __name__ == "__main__":
    main()
