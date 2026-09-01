"""Met à jour la couche « base » (dossier base/) depuis le dépôt site-base.

Le projet (dossier app/) n'est JAMAIS touché : on ne remplace que base/panel/.
Utilisé par le bouton « Mettre à jour la base » (Paramètres) et par la commande :

    python manage.py sync_base [--ref 2.0.0]

Config (env ou app.config) :
    BASE_REPO_URL   dépôt source de la base (défaut : SuperNon0/Site-base)
    BASE_REPO_REF   version/branche à installer (défaut : dernière version « couches »)
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]  # …/base
_VERSION_RE = re.compile(r"^v?\d+(\.\d+)*$")
DEFAULT_URL = "https://github.com/SuperNon0/Site-base.git"


def _cfg(name: str, default: str = "") -> str:
    try:
        from flask import current_app
        return current_app.config.get(name, None) or os.getenv(name, default)
    except Exception:
        return os.getenv(name, default)


def _run(cmd: list[str], timeout: float = 180) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, "LC_ALL": "C"})
        return p.returncode, p.stdout, p.stderr
    except Exception as exc:  # pragma: no cover
        return -1, "", str(exc)


def read_version() -> str | None:
    f = BASE_DIR / ".base-version"
    return f.read_text(encoding="utf-8").strip() if f.exists() else None


def _semver(t: str) -> list[int]:
    return [int(x) for x in t.lstrip("v").split(".") if x.isdigit()]


def latest_ref(url: str) -> str | None:
    """Dernière version « en couches » (majeure ≥ 2) publiée sur le dépôt."""
    rc, out, _ = _run(["git", "ls-remote", "--tags", url], 60)
    if rc != 0:
        return None
    tags = []
    for line in out.splitlines():
        name = line.split("refs/tags/")[-1].strip()
        if name.endswith("^{}") or not _VERSION_RE.match(name):
            continue
        tags.append(name)
    tags.sort(key=_semver, reverse=True)
    couches = [t for t in tags if _semver(t) and _semver(t)[0] >= 2]
    return (couches or tags or [None])[0]


def sync(ref: str | None = None) -> dict:
    url = _cfg("BASE_REPO_URL", DEFAULT_URL)
    ref = ref or _cfg("BASE_REPO_REF", "") or latest_ref(url)
    if not ref:
        return {"ok": False, "error": "Aucune version de base trouvée sur le dépôt."}

    before = read_version()
    tmp = tempfile.mkdtemp()
    try:
        rc, _out, err = _run(["git", "clone", "--depth", "1", "--branch", ref, url, tmp], 300)
        if rc != 0:
            return {"ok": False, "error": f"Clone de « {ref} » échoué : {err[:300]}"}
        src = Path(tmp) / "base" / "panel"
        if not src.is_dir():
            return {"ok": False,
                    "error": f"La version « {ref} » n'a pas de couche base/ "
                             "(ce n'est pas un modèle en couches)."}
        # Remplace UNIQUEMENT base/panel (app/ n'est pas touché).
        dst = BASE_DIR / "panel"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
        src_ver = (Path(tmp) / "base" / ".base-version")
        version = src_ver.read_text(encoding="utf-8").strip() if src_ver.exists() else ref.lstrip("v")
        (BASE_DIR / ".base-version").write_text(version + "\n", encoding="utf-8")
        return {"ok": True, "from": before, "to": version}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    ref = None
    args = sys.argv[1:]
    if args and args[0] == "--ref" and len(args) > 1:
        ref = args[1]
    res = sync(ref)
    if res.get("ok"):
        print(f"✓ Base mise à jour : {res.get('from')} → {res.get('to')}")
        sys.exit(0)
    print(f"✗ {res.get('error')}")
    sys.exit(1)


if __name__ == "__main__":
    main()
