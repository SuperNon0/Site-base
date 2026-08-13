"""Opérations système : mise à jour Git + redémarrage du service, depuis l'UI.

Inspiré de BotPanel. Le bouton « Mettre à jour » des Paramètres appelle :
  - POST /api/system/update  → git fetch + reset --hard origin/<branche> + pip install
  - POST /api/system/restart → redémarre le service systemd

Prérequis serveur (posés par deploy/install_lxc.sh) :
  - /opt/site-base appartient à l'utilisateur du service (sitebase) → pas de sudo
    pour git/pip.
  - Une règle sudoers autorise le redémarrage sans mot de passe :
        sitebase ALL=NOPASSWD: /bin/systemctl restart site-base
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from flask import Blueprint, current_app, jsonify, session

from ..auth import super_admin_required

bp = Blueprint("system", __name__)

# Racine du projet : panel/routes/system_routes.py → remonter de 2 niveaux.
INSTALL_DIR = Path(__file__).resolve().parents[2]
SERVICE_NAME = "site-base"


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
@super_admin_required
def info():
    is_git = (INSTALL_DIR / ".git").exists()
    data = {"install_dir": str(INSTALL_DIR), "is_git": is_git,
            "commit": None, "branch": None, "service_active": None}
    if is_git:
        data["commit"] = _run(["git", "rev-parse", "--short", "HEAD"], 5)["stdout"].strip() or None
        data["branch"] = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], 5)["stdout"].strip() or None
    active = _run(["systemctl", "is-active", SERVICE_NAME], 5)
    data["service_active"] = (active["stdout"].strip() == "active") if active["exit_code"] >= 0 else None
    return jsonify(data)


@bp.route("/api/system/update", methods=["POST"])
@super_admin_required
def update():
    if _blocked_by_impersonation():
        return jsonify({"ok": False, "error": "Reviens à ton compte avant de mettre à jour."}), 403
    if not (INSTALL_DIR / ".git").exists():
        return jsonify({"ok": False, "error": f"{INSTALL_DIR} n'est pas un dépôt git."}), 400

    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], 5)["stdout"].strip() or "main"
    remote_ref = f"origin/{branch}"

    fetch = _run(["git", "fetch", "--prune", "origin"], 120)
    if fetch["exit_code"] != 0:
        return jsonify({"ok": False, "fetch": fetch})

    reset = _run(["git", "reset", "--hard", remote_ref], 60)
    pip = None
    venv_pip = INSTALL_DIR / ".venv" / "bin" / "pip"
    if reset["exit_code"] == 0 and venv_pip.exists():
        pip = _run([str(venv_pip), "install", "-q", "-r", str(INSTALL_DIR / "requirements.txt")], 180)

    ok = reset["exit_code"] == 0 and (pip is None or pip["exit_code"] == 0)
    return jsonify({"ok": ok, "branch": branch, "fetch": fetch, "reset": reset, "pip": pip})


@bp.route("/api/system/restart", methods=["POST"])
@super_admin_required
def restart():
    if _blocked_by_impersonation():
        return jsonify({"ok": False, "error": "Reviens à ton compte d'abord."}), 403
    # Redémarrage détaché (laisse le temps de répondre avant que systemd coupe).
    try:
        subprocess.Popen(
            ["bash", "-c", f"sleep 1; sudo systemctl restart {SERVICE_NAME}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception as exc:  # pragma: no cover
        return jsonify({"ok": False, "error": str(exc)}), 500
    return jsonify({"ok": True, "status": "restarting"})
