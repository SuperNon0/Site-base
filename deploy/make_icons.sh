#!/usr/bin/env bash
#
# Génère les icônes PNG de la PWA depuis panel/static/logo.svg
# (pour iOS « Ajouter à l'écran d'accueil » — Android utilise déjà le SVG).
#
#   bash deploy/make_icons.sh
#
# Utilise rsvg-convert, inkscape ou ImageMagick (le premier disponible).
# Remplace d'abord panel/static/logo.svg par ton logo si tu veux ta propre icône.
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
SVG="${HERE}/panel/static/logo.svg"
OUT="${HERE}/panel/static/icons"
mkdir -p "${OUT}"

render() {  # render <taille> <fichier>
  local size="$1" file="$2"
  if command -v rsvg-convert >/dev/null 2>&1; then
    rsvg-convert -w "${size}" -h "${size}" "${SVG}" -o "${file}"
  elif command -v inkscape >/dev/null 2>&1; then
    inkscape "${SVG}" -w "${size}" -h "${size}" -o "${file}" >/dev/null 2>&1
  elif command -v convert >/dev/null 2>&1; then
    convert -background none -resize "${size}x${size}" "${SVG}" "${file}"
  elif command -v magick >/dev/null 2>&1; then
    magick -background none "${SVG}" -resize "${size}x${size}" "${file}"
  else
    echo "✗ Aucun outil de rendu SVG (rsvg-convert / inkscape / ImageMagick)."
    echo "  Installe-en un (ex. apt-get install librsvg2-bin) puis relance."
    exit 1
  fi
}

for s in 180 192 512; do
  render "${s}" "${OUT}/icon-${s}.png"
  echo "✓ icon-${s}.png"
done
echo "Icônes générées dans ${OUT}. (Le manifeste les utilisera automatiquement.)"
