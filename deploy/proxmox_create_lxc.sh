#!/usr/bin/env bash
#
# Site de base — création d'un conteneur LXC + installation, EN UNE COMMANDE.
#
# À lancer SUR L'HÔTE PROXMOX (le shell du nœud, ex. root@pve). Le script :
#   1. crée un conteneur LXC Debian 12 (télécharge le template si besoin),
#   2. le démarre et attend le réseau (DHCP),
#   3. installe le site dedans (bootstrap base + .env + service systemd),
#   4. affiche l'IP du conteneur et les identifiants.
#
# Exemple (installer VTC depuis sa branche de migration) :
#   ADMIN_EMAIL=toi@gmail.com \
#   REPO_URL=https://github.com/SuperNon0/VTC.git \
#   REPO_REF=claude/migration-nouveau-socle \
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/SuperNon0/Site-base/main/deploy/proxmox_create_lxc.sh)"
#
# Réglages (variables d'environnement, toutes optionnelles sauf ADMIN_EMAIL conseillé) :
#   VMID=              id du conteneur (défaut : prochain id libre)
#   CT_HOSTNAME=       nom du conteneur (défaut : site-base)
#   STORAGE=           stockage du rootfs (défaut : local-lvm)
#   TEMPLATE_STORAGE=  stockage des templates (défaut : local)
#   BRIDGE=            pont réseau (défaut : vmbr0)
#   CORES=  MEMORY=  SWAP=  DISK=   (défaut : 1 / 512 Mo / 512 Mo / 4 Go)
#   ADMIN_EMAIL=  ADMIN_PASSWORD=   compte super-admin (comme install.sh)
#   REPO_URL=  REPO_REF=            projet à installer (défaut : site-base / main)
#   BASE_REPO_REF=main              suit la base au fil de l'eau (pas de tag à publier)
#
set -euo pipefail

CT_HOSTNAME="${CT_HOSTNAME:-site-base}"
STORAGE="${STORAGE:-local-lvm}"
TEMPLATE_STORAGE="${TEMPLATE_STORAGE:-local}"
BRIDGE="${BRIDGE:-vmbr0}"
CORES="${CORES:-1}"
MEMORY="${MEMORY:-512}"
SWAP="${SWAP:-512}"
DISK="${DISK:-4}"
ADMIN_EMAIL="${ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
REPO_URL="${REPO_URL:-https://github.com/SuperNon0/Site-base.git}"
REPO_REF="${REPO_REF:-}"
BASE_REPO_REF="${BASE_REPO_REF:-}"
INSTALLER_URL="${INSTALLER_URL:-https://raw.githubusercontent.com/SuperNon0/Site-base/main/install.sh}"

if ! command -v pct >/dev/null 2>&1; then
  echo "✗ Ce script doit tourner SUR L'HÔTE PROXMOX (commande 'pct' introuvable)." >&2
  echo "  Tu es peut-être dans le conteneur : lance plutôt install.sh." >&2
  exit 1
fi

# En cas d'échec pendant la création/démarrage du conteneur, on oriente vers la VM.
_on_error() {
  echo "" >&2
  echo "✗ La création/installation du conteneur LXC a échoué." >&2
  echo "  Si ton nœud n'accepte pas ce LXC (nesting/systemd, stockage…), bascule" >&2
  echo "  en machine virtuelle : voir « Repli VM » dans docs/deploiement-proxmox.md" >&2
  echo "  (crée la VM, puis lance install.sh À L'INTÉRIEUR — même commande)." >&2
}
trap _on_error ERR

# --- VMID : fourni, sinon prochain id libre ------------------------------------
if [ -z "${VMID:-}" ]; then
  VMID="$(pvesh get /cluster/nextid 2>/dev/null || echo 120)"
fi
echo ">>> Conteneur LXC #${VMID} (${CT_HOSTNAME})"

# --- Template Debian 12 : réutilise s'il est là, sinon télécharge --------------
TMPL="$(pveam list "${TEMPLATE_STORAGE}" 2>/dev/null | awk '/debian-12-standard/ {print $1}' | head -1)"
if [ -z "${TMPL}" ]; then
  echo ">>> Téléchargement du template Debian 12"
  pveam update >/dev/null 2>&1 || true
  AVAIL="$(pveam available --section system 2>/dev/null | awk '/debian-12-standard/ {print $2}' | sort | tail -1)"
  if [ -z "${AVAIL}" ]; then
    echo "✗ Aucun template debian-12-standard disponible via pveam." >&2
    exit 1
  fi
  pveam download "${TEMPLATE_STORAGE}" "${AVAIL}"
  TMPL="${TEMPLATE_STORAGE}:vztmpl/${AVAIL}"
fi
echo ">>> Template : ${TMPL}"

# --- Création + démarrage ------------------------------------------------------
echo ">>> Création du conteneur"
pct create "${VMID}" "${TMPL}" \
  --hostname "${CT_HOSTNAME}" \
  --cores "${CORES}" --memory "${MEMORY}" --swap "${SWAP}" \
  --rootfs "${STORAGE}:${DISK}" \
  --net0 "name=eth0,bridge=${BRIDGE},ip=dhcp" \
  --unprivileged 1 --features nesting=1 \
  --onboot 1

echo ">>> Démarrage"
pct start "${VMID}"

# --- Attente du réseau (DHCP) --------------------------------------------------
echo -n ">>> Attente d'une IP"
IP=""
for _ in $(seq 1 30); do
  IP="$(pct exec "${VMID}" -- hostname -I 2>/dev/null | awk '{print $1}')"
  [ -n "${IP}" ] && break
  echo -n "."; sleep 2
done
echo ""
if [ -z "${IP}" ]; then
  echo "✗ Le conteneur n'a pas obtenu d'IP (DHCP). Vérifie le bridge ${BRIDGE}." >&2
  exit 1
fi
echo ">>> IP du conteneur : ${IP}"

# --- Installation applicative DANS le conteneur --------------------------------
echo ">>> Dépendances minimales dans le conteneur"
pct exec "${VMID}" -- bash -c "apt-get update -y && apt-get install -y --no-install-recommends curl git ca-certificates"

echo ">>> Récupération de l'installateur"
pct exec "${VMID}" -- bash -c "curl -fsSL '${INSTALLER_URL}' -o /root/install.sh"

echo ">>> Installation du site (dans le conteneur)"
pct exec "${VMID}" -- env \
  ADMIN_EMAIL="${ADMIN_EMAIL}" \
  ADMIN_PASSWORD="${ADMIN_PASSWORD}" \
  REPO_URL="${REPO_URL}" \
  REPO_REF="${REPO_REF}" \
  BASE_REPO_REF="${BASE_REPO_REF}" \
  bash /root/install.sh

echo ""
echo "════════════════════════════════════════════════════════════════"
echo " Conteneur #${VMID} (${CT_HOSTNAME}) prêt."
echo " IP du conteneur            : ${IP}"
echo " Le service écoute en local (127.0.0.1:8000) DANS le conteneur."
echo " Étapes restantes :"
echo "  • Exposer via Cloudflare Tunnel (docs/deploiement-proxmox.md §3)"
echo "  • Ou, pour tester sur le LAN : dans le conteneur, remplace"
echo "    127.0.0.1:8000 par 0.0.0.0:8000 dans le service, puis"
echo "    ouvre http://${IP}:8000"
echo "  • Console du conteneur : pct enter ${VMID}"
echo "════════════════════════════════════════════════════════════════"
