#!/usr/bin/env bash
#
# socle-lite — réinitialise le mot de passe de SECOURS LOCAL (ADMIN_PASSWORD).
#
# Le socle-lite n'a pas de base de données : le mot de passe local est simplement
# la variable ADMIN_PASSWORD du .env. Ce script la met à jour proprement et
# recharge le service.
#
# Usage (en root sur le serveur) :
#   sudo bash deploy/reset-password.sh                 # génère un mot de passe et l'affiche
#   sudo bash deploy/reset-password.sh 'MonNouveauMdp' # fixe un mot de passe précis
#
# Réglages (variables d'environnement, si ton install diffère) :
#   INSTALL_DIR=/opt/site-base   dossier de l'appli (défaut)
#   SERVICE=site-base            nom du service systemd (défaut)
#   ENV_FILE=$INSTALL_DIR/.env   chemin du .env
#
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/site-base}"
SERVICE="${SERVICE:-site-base}"
ENV_FILE="${ENV_FILE:-${INSTALL_DIR}/.env}"

NEW="${1:-}"
GENERATED=""
if [ -z "${NEW}" ]; then
    NEW="$(python3 -c 'import secrets; print(secrets.token_urlsafe(12))')"
    GENERATED="1"
fi

if [ ! -f "${ENV_FILE}" ]; then
    echo "✗ .env introuvable : ${ENV_FILE}" >&2
    echo "  Précise-le : ENV_FILE=/chemin/.env sudo bash deploy/reset-password.sh" >&2
    exit 1
fi

# Mise à jour sûre de la ligne ADMIN_PASSWORD (la valeur est passée en argument,
# jamais interpolée dans un sed → aucun souci de caractères spéciaux).
python3 - "${ENV_FILE}" "${NEW}" <<'PY'
import sys
path, value = sys.argv[1], sys.argv[2]
lines = open(path, encoding="utf-8").read().splitlines()
out, found = [], False
for line in lines:
    if line.startswith("ADMIN_PASSWORD="):
        out.append("ADMIN_PASSWORD=" + value); found = True
    else:
        out.append(line)
if not found:
    out.append("ADMIN_PASSWORD=" + value)
open(path, "w", encoding="utf-8").write("\n".join(out) + "\n")
PY

# Recharge le service s'il existe.
if command -v systemctl >/dev/null 2>&1 \
   && systemctl list-unit-files 2>/dev/null | grep -q "^${SERVICE}\.service"; then
    systemctl restart "${SERVICE}"
    echo "→ service ${SERVICE} redémarré."
else
    echo "→ redémarre le service manuellement pour appliquer (ex. systemctl restart ${SERVICE})."
fi

echo "✓ Mot de passe de secours local mis à jour dans ${ENV_FILE}."
if [ -n "${GENERATED}" ]; then
    echo "  Nouveau mot de passe : ${NEW}   ← note-le !"
fi

# Rappel utile : si le login local est désactivé, ce mot de passe est inerte.
if grep -qiE '^ALLOW_LOCAL_LOGIN=(false|0|no|off)$' "${ENV_FILE}"; then
    echo "  (note : ALLOW_LOCAL_LOGIN est désactivé → l'entrée se fait uniquement par Cloudflare.)"
fi
