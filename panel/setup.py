"""Assistant de création de site : demande chaque permission, écrit `.env`.

À lancer une fois quand on démarre un nouveau projet depuis le site de base :

    python -m panel.setup                 # interactif : pose chaque permission
    python -m panel.setup --preset hub    # hub : gestion des comptes complète
    python -m panel.setup --preset perso  # site perso : auto-actif, MAJ off

Chaque permission se répond par : super_admin | membre | off
(voir docs/permissions.md). Les autres réglages (Cloudflare, BotPanel, secret…)
restent à compléter dans `.env`.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .permissions import CAPABILITIES, LEVELS

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"

# Presets : niveau de chaque capability.
PRESETS = {
    "hub": {  # la home page : gestion des comptes centralisée
        "account_management": "super_admin",
        "profiles": "super_admin",
        "admin_password": "super_admin",
        "site_update": "super_admin",
    },
    "perso": {  # un site applicatif : accès auto, pas de gestion ni de MAJ
        "account_management": "off",
        "profiles": "super_admin",
        "admin_password": "super_admin",
        "site_update": "off",
    },
}


def _ask(key: str) -> str:
    label, desc, default = CAPABILITIES[key]
    print(f"\n• {label}\n  {desc}")
    while True:
        rep = input(f"  Niveau [{'/'.join(LEVELS)}] (défaut {default}) : ").strip().lower()
        if not rep:
            return default
        if rep in LEVELS:
            return rep
        print("  ↳ réponds par : " + ", ".join(LEVELS))


def _write_env(levels: dict[str, str]) -> None:
    # Part d'un .env existant, sinon du modèle .env.example.
    if ENV.exists():
        lines = ENV.read_text(encoding="utf-8").splitlines()
    elif ENV_EXAMPLE.exists():
        lines = ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    def set_key(lines: list[str], key: str, val: str) -> list[str]:
        prefix = f"{key}="
        for i, ln in enumerate(lines):
            if ln.startswith(prefix) or ln.startswith(f"# {prefix}"):
                lines[i] = f"{key}={val}"
                return lines
        lines.append(f"{key}={val}")
        return lines

    for cap, lvl in levels.items():
        lines = set_key(lines, f"CAP_{cap.upper()}", lvl)

    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    preset = None
    if "--preset" in sys.argv:
        i = sys.argv.index("--preset")
        preset = sys.argv[i + 1] if i + 1 < len(sys.argv) else None
        if preset not in PRESETS:
            print(f"Preset inconnu. Choix : {', '.join(PRESETS)}")
            sys.exit(1)

    print("=== Permissions du site (voir docs/permissions.md) ===")
    if preset:
        levels = dict(PRESETS[preset])
        print(f"Preset « {preset} » :")
        for k, v in levels.items():
            print(f"  - {CAPABILITIES[k][0]} : {v}")
    else:
        print("Réponds pour chaque fonctionnalité : qui a le droit ?")
        levels = {key: _ask(key) for key in CAPABILITIES}

    _write_env(levels)
    print(f"\n✓ Permissions écrites dans {ENV}")
    if levels.get("account_management") == "off":
        print("  → Site « perso » : les utilisateurs (filtrés par Cloudflare) sont")
        print("    créés automatiquement en actif ; gestion/ blocage se font au hub.")
    print("  Pense à compléter le reste de .env (SECRET_KEY, Cloudflare, BotPanel…).")


if __name__ == "__main__":
    main()
