#!/usr/bin/env python3
"""Amorce (ou réinstalle) la couche « base » depuis le dépôt site-base.

Dans le modèle en couches, un PROJET ne versionne PAS `base/` : la fondation est
fournie par ton dépôt site-base et récupérée ici. Ce script est volontairement
AUTONOME (bibliothèque standard uniquement, aucun import de `panel`) : il doit
pouvoir tourner alors que `base/` n'existe pas encore.

    python bootstrap_base.py                 # dernière version publiée, sinon main
    python bootstrap_base.py --ref 2.1.0     # une version précise
    BASE_REPO_REF=une-branche python bootstrap_base.py   # une branche précise

Ensuite : `python run.py`. Pour METTRE À JOUR la base après coup, utilise le
bouton « Mettre à jour la base » (Paramètres) ou `python manage.py sync_base` —
ou relance ce script.

Config (variables d'environnement) :
    BASE_REPO_URL   dépôt source (défaut : https://github.com/SuperNon0/Site-base.git)
    BASE_REPO_REF   version (tag) ou branche à installer (sinon : dernière « couches »)
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEST = ROOT / "base"
DEFAULT_URL = "https://github.com/SuperNon0/Site-base.git"
_VERSION_RE = re.compile(r"^v?\d+(\.\d+)*$")


def _run(cmd: list[str], timeout: float = 300) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, "LC_ALL": "C"})
        return p.returncode, p.stdout, p.stderr
    except Exception as exc:  # pragma: no cover
        return -1, "", str(exc)


def _semver(t: str) -> list[int]:
    return [int(x) for x in t.lstrip("v").split(".") if x.isdigit()]


def _latest_ref(url: str) -> str | None:
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
    couches = sorted((t for t in tags if _semver(t) and _semver(t)[0] >= 2),
                     key=_semver, reverse=True)
    return couches[0] if couches else None


def _clone_base(url: str, ref: str) -> str | None:
    """Clone `url` à `ref` dans un dossier temporaire ; renvoie le chemin de la
    couche base/ si elle existe, sinon None (et nettoie)."""
    tmp = tempfile.mkdtemp()
    print(f">>> Récupération de la base « {ref} » depuis {url}")
    rc, _out, err = _run(["git", "clone", "--depth", "1", "--branch", ref, url, tmp], 300)
    if rc == 0 and (Path(tmp) / "base" / "panel").is_dir():
        return tmp
    if rc != 0:
        print(f"   (« {ref} » : clone échoué : {err[:150].strip()})", file=sys.stderr)
    else:
        print(f"   (« {ref} » : pas de couche base/ — ignorée)", file=sys.stderr)
    shutil.rmtree(tmp, ignore_errors=True)
    return None


def main() -> None:
    args = sys.argv[1:]
    ref = None
    if args and args[0] == "--ref" and len(args) > 1:
        ref = args[1]
    ref = ref or os.getenv("BASE_REPO_REF") or None
    url = os.getenv("BASE_REPO_URL", DEFAULT_URL)

    # Candidats, dans l'ordre : version demandée → dernière version publiée →
    # branche « main ». On saute tout candidat qui n'a pas de couche base/ (ex.
    # un tag mal placé sur l'ancien modèle « à plat ») : jamais de casse.
    if ref:
        candidates = [ref]
    else:
        latest = _latest_ref(url)
        candidates = ([latest] if latest else []) + ["main"]

    tmp = None
    for cand in candidates:
        tmp = _clone_base(url, cand)
        if tmp:
            break
    if not tmp:
        print("✗ Aucune version exploitable trouvée (essayés : "
              f"{', '.join(candidates)}).", file=sys.stderr)
        sys.exit(1)

    try:
        src = Path(tmp) / "base"
        if DEST.exists():
            shutil.rmtree(DEST)
        shutil.copytree(src, DEST, ignore=shutil.ignore_patterns("__pycache__"))
        version = "?"
        vf = DEST / ".base-version"
        if vf.exists():
            version = vf.read_text(encoding="utf-8").strip()
        print(f"✓ Base installée dans {DEST}  (version {version}). Lance : python run.py")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
