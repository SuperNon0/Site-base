"""PWA : manifeste web + service worker, pilotés par la marque (.env).

Rend le site **installable** (« Ajouter à l'écran d'accueil ») et ouvrable comme
une app autonome. Le logo = `panel/static/logo.svg` (remplace-le pour changer
l'icône). Les icônes PNG (iOS) sont utilisées si présentes dans
`panel/static/icons/` — génère-les avec `deploy/make_icons.sh`.
"""

from __future__ import annotations

import os

from flask import Blueprint, Response, current_app, json, url_for

bp = Blueprint("pwa", __name__)


def _has(rel: str) -> bool:
    return os.path.isfile(os.path.join(current_app.static_folder, rel))


@bp.route("/manifest.webmanifest")
def manifest():
    brand = f"{current_app.config['BRAND_PREFIX']}{current_app.config['BRAND_SUFFIX']}"
    icons = [{
        "src": url_for("static", filename="logo.svg"),
        "sizes": "any", "type": "image/svg+xml", "purpose": "any",
    }]
    # Préfère les PNG (maskable) s'ils ont été générés.
    for size in (192, 512):
        rel = f"icons/icon-{size}.png"
        if _has(rel):
            icons.append({"src": url_for("static", filename=rel),
                          "sizes": f"{size}x{size}", "type": "image/png",
                          "purpose": "maskable any"})
    data = {
        "name": brand,
        "short_name": brand,
        "description": current_app.config.get("BRAND_BADGE", ""),
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#0e0f11",
        "theme_color": "#0e0f11",
        "icons": icons,
    }
    return Response(json.dumps(data), mimetype="application/manifest+json")


_SW = """
const CACHE = 'sitebase-v1';
self.addEventListener('install', function (e) { self.skipWaiting(); });
self.addEventListener('activate', function (e) { e.waitUntil(self.clients.claim()); });
self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  // Réseau d'abord ; on met en cache les statiques pour l'usage hors-ligne.
  e.respondWith(
    fetch(req).then(function (r) {
      if (req.url.indexOf('/static/') !== -1) {
        var copy = r.clone();
        caches.open(CACHE).then(function (c) { c.put(req, copy); });
      }
      return r;
    }).catch(function () { return caches.match(req); })
  );
});
"""


@bp.route("/sw.js")
def sw():
    return Response(_SW, mimetype="application/javascript")
