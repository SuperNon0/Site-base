#!/usr/bin/env bash
#
# Site de base — installation en une commande (Debian/Ubuntu, LXC ou VM), en root.
#
#   ADMIN_EMAIL=toi@gmail.com bash -c "$(curl -fsSL https://raw.githubusercontent.com/SuperNon0/Site-base/main/install.sh)"
#
# Options (variables d'environnement) :
#   ADMIN_EMAIL=...      e-mail Google du super-admin (Cloudflare)
#   ADMIN_PASSWORD=...   mot de passe admin LAN (sinon généré aléatoirement)
#   REPO_URL=...         dépôt du PROJET à installer (défaut : SuperNon0/Site-base)
#   REPO_REF=...         branche/tag du PROJET (défaut : branche par défaut)
#   BASE_REPO_REF=...    ref de la couche BASE suivie par « Mettre à jour la base »
#                        (ex. main = toujours à jour sans tag ; défaut : dernière version publiée)
#
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/SuperNon0/Site-base.git}"
REPO_REF="${REPO_REF:-}"
INSTALL_DIR="/opt/site-base"

if [ "$(id -u)" -ne 0 ]; then
  echo "À lancer en root (ou via sudo)." >&2
  exit 1
fi

echo ">>> Dépendances minimales (git)"
apt-get update -y
apt-get install -y --no-install-recommends git ca-certificates

echo ">>> Récupération du code (${REPO_URL}${REPO_REF:+ @ ${REPO_REF}})"
if [ -d "${INSTALL_DIR}/.git" ]; then
  if [ -n "${REPO_REF}" ]; then
    git -C "${INSTALL_DIR}" fetch --depth 1 origin "${REPO_REF}"
    git -C "${INSTALL_DIR}" checkout -f FETCH_HEAD
  else
    git -C "${INSTALL_DIR}" pull --ff-only
  fi
else
  git clone --depth 1 ${REPO_REF:+--branch "${REPO_REF}"} "${REPO_URL}" "${INSTALL_DIR}"
fi

# ADMIN_EMAIL / ADMIN_PASSWORD / BASE_REPO_REF transmis à l'install + au bootstrap.
export ADMIN_EMAIL="${ADMIN_EMAIL:-}"
export ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
# BASE_REPO_REF : ref de la couche BASE (≠ REPO_REF qui est la branche du PROJET).
# Ex. BASE_REPO_REF=main pour suivre la base au fil de l'eau (sans publier de tag).
export BASE_REPO_REF="${BASE_REPO_REF:-}"

echo ">>> Installation"
bash "${INSTALL_DIR}/deploy/install_lxc.sh"
