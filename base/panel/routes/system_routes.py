"""Opérations système : mise à jour Git + redémarrage du service, depuis l'UI.

Inspiré de BotPanel. Le bouton « Mettre à jour » des Paramètres appelle :
  - POST /api/system/update  → passe à la dernière **version** (tag Git), pip install
  - POST /api/system/restart → redémarre le service systemd

Modèle de versions : les releases sont des **tags** `vX.Y.Z` (v1.0.0, v1.1.0…).
La mise à jour saute à la dernière version publiée. S'il n'existe encore aucun
tag, on retombe sur la tête de la branche courante (pour que ça marche avant la
première release). Un tag précis peut être visé (rollback) : {"ref": "v1.0.0"}.

Prérequis serveur (posés par deploy/install_lxc.sh) :
  - /opt/site-base appartient à l'utilisateur du service (sitebase) → pas de sudo
    pour git/pip.
  - Une règle sudoers autorise le redémarrage sans mot de passe :
        sitebase ALL=NOPASSWD: /bin/systemctl restart site-base
"""

from __future__ import annotations

import os
import re
import shlex
import signal
import subprocess
from pathlib import Path

from flask import Blueprint, jsonify, request, session

from ..permissions import require_capability

bp = Blueprint("system", __name__)

# Racine du projet : base/panel/routes/system_routes.py → remonter de 3 niveaux.
INSTALL_DIR = Path(__file__).resolve().parents[3]
# Dossier de la couche « base » (verrouillée), cible de la mise à jour de base.
BASE_DIR = Path(__file__).resolve().parents[2]
SERVICE_NAME = "site-base"

# Un tag de version : 1.2.3 ou v1.2.3 (le préfixe « v » est optionnel).
_VERSION_RE = re.compile(r"^v?\d+(\.\d+)*$")


def _version_tags() -> list[str]:
    """Tags de version présents en local, du plus récent au plus ancien (semver)."""
    out = _run(["git", "tag", "-l", "--sort=-v:refname"], 10)["stdout"]
    return [t for t in out.split() if _VERSION_RE.match(t)]


def _current_version() -> str | None:
    """Version courante : tag exact si on est dessus, sinon description lisible."""
    exact = _run(["git", "describe", "--tags", "--exact-match"], 5)
    if exact["exit_code"] == 0 and exact["stdout"].strip():
        return exact["stdout"].strip()
    desc = _run(["git", "describe", "--tags", "--always"], 5)["stdout"].strip()
    return desc or None


def _run(cmd: list[str], timeout: float = 120.0) -> dict:
    """Exécute une commande, renvoie exit_code/stdout/stderr."""
    try:
        proc = subprocess.run(
            cmd, cwd=str(INSTALL_DIR), capture_output=True, text=True,
            timeout=timeout, env={"LC_ALL": "C", "PATH": "/usr/bin:/bin:/usr/local/bin"},
        )
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "command": " ".join(shlex.quote(c) for c in cmd),
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": "Délai dépassé.",
                "command": " ".join(shlex.quote(c) for c in cmd)}
    except FileNotFoundError as exc:
        return {"exit_code": -1, "stdout": "", "stderr": str(exc),
                "command": " ".join(shlex.quote(c) for c in cmd)}


def _blocked_by_impersonation() -> bool:
    return bool(session.get("impersonator_id"))


@bp.route("/api/system/info")
@require_capability("site_update")
def info():
    is_git = (INSTALL_DIR / ".git").exists()
    data = {"install_dir": str(INSTALL_DIR), "is_git": is_git,
            "version": None, "branch": None, "service_active": None}
    if is_git:
        data["version"] = _current_version()
        data["branch"] = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], 5)["stdout"].strip() or None
    active = _run(["systemctl", "is-active", SERVICE_NAME], 5)
    data["service_active"] = (active["stdout"].strip() == "active") if active["exit_code"] >= 0 else None
    return jsonify(data)


@bp.route("/api/system/update", methods=["POST"])
@require_capability("site_update")
def update():
    if _blocked_by_impersonation():
        return jsonify({"ok": False, "error": "Reviens à ton compte avant de mettre à jour."}), 403
    if not (INSTALL_DIR / ".git").exists():
        return jsonify({"ok": False, "error": f"{INSTALL_DIR} n'est pas un dépôt git."}), 400

    # Version visée : celle demandée (rollback), sinon la dernière version publiée.
    requested = (request.get_json(silent=True) or {}).get("ref") if request.data else None
    before = _current_version()

    # Récupère commits ET tags de version.
    fetch = _run(["git", "fetch", "--tags", "--prune", "--force", "origin"], 120)
    if fetch["exit_code"] != 0:
        return jsonify({"ok": False, "fetch": fetch})

    tags = _version_tags()
    if requested:
        if not _VERSION_RE.match(requested) or requested not in tags:
            return jsonify({"ok": False, "error": f"Version inconnue : {requested}"}), 400
        target, mode = requested, "tag"
    elif tags:
        target, mode = tags[0], "tag"  # la plus récente
    else:
        # Aucun tag encore : on suit la tête de la branche courante.
        branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], 5)["stdout"].strip() or "main"
        target, mode = f"origin/{branch}", "branch"

    if mode == "tag":
        checkout = _run(["git", "-c", "advice.detachedHead=false", "checkout", "--force", target], 60)
    else:
        checkout = _run(["git", "reset", "--hard", target], 60)

    pip = None
    venv_pip = INSTALL_DIR / ".venv" / "bin" / "pip"
    if checkout["exit_code"] == 0 and venv_pip.exists():
        pip = _run([str(venv_pip), "install", "-q", "-r", str(INSTALL_DIR / "requirements.txt")], 180)

    ok = checkout["exit_code"] == 0 and (pip is None or pip["exit_code"] == 0)
    return jsonify({
        "ok": ok, "mode": mode, "from": before, "to": (target if mode == "tag" else _current_version()),
        "latest": tags[0] if tags else None,
        "fetch": fetch, "checkout": checkout, "pip": pip,
    })


def _gunicorn_master_pid() -> int | None:
    """PID du master gunicorn (le parent), si on tourne bien sous gunicorn."""
    ppid = os.getppid()
    try:
        with open(f"/proc/{ppid}/cmdline", "rb") as f:
            cmdline = f.read().decode("utf-8", "replace")
        if "gunicorn" in cmdline:
            return ppid
    except OSError:
        pass
    return None


@bp.route("/api/system/restart", methods=["POST"])
@require_capability("site_update")
def restart():
    if _blocked_by_impersonation():
        return jsonify({"ok": False, "error": "Reviens à ton compte d'abord."}), 403
    # Rechargement gracieux : SIGHUP au master gunicorn → nouveaux workers avec le
    # code à jour, sans sudo ni coupure. (Le master relit et relance les workers.)
    master = _gunicorn_master_pid()
    if master:
        try:
            os.kill(master, signal.SIGHUP)
        except OSError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
        return jsonify({"ok": True, "status": "reloading"})
    # Repli (hors gunicorn, ex. dev) : rien à recharger automatiquement.
    return jsonify({"ok": False, "error": "Hors gunicorn : relance le service à la main."}), 200
