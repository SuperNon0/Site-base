# socle-lite

**Socle minimal** pour un site **sans comptes** (un seul utilisateur, ou accès
restreint par Cloudflare). Il fournit **uniquement** :

- ✅ **Vérification Cloudflare Access** (JWT `RS256` + `aud` + `iss`) — code repris
  **à l'identique du site-base** (testé). On ne fait jamais confiance à l'en-tête seul.
- ✅ **Secours local** (mot de passe LAN), désactivable.
- ✅ **Un seul statut** : authentifié ou refusé. **Pas de comptes, pas de rôles,
  pas de page Paramètres.**
- ✅ Le **thème** (même look que tes autres sites).

C'est le bon choix pour un **petit outil propre et autonome**. Pour un site
multi-utilisateurs (comptes, rôles, validation…), utilise le **site-base** complet.

## Démarrer

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # renseigne SECRET_KEY ; ADMIN_PASSWORD pour le secours local
python run.py             # http://127.0.0.1:8000
```

En dev sans Cloudflare : `CF_VERIFY_JWT=false` + `ALLOW_LOCAL_LOGIN=true` + un
`ADMIN_PASSWORD` → connexion par mot de passe.

## Comment ça marche

```
Visiteur ──► /gateway
   ├─ e-mail Cloudflare vérifié  → (option : dans ALLOWED_EMAILS ?) → entre
   └─ pas de Cloudflare (LAN)    → login mot de passe (si activé), sinon « Accès refusé »
```

- **`ALLOW_LOCAL_LOGIN=false`** (ou `ADMIN_PASSWORD` vide) → entrée **uniquement**
  par Cloudflare ; un accès direct (LAN) reçoit **403** (même en POST).
- **`ALLOWED_EMAILS`** (optionnel) → restreint aussi côté appli. Vide = on fait
  confiance à la liste d'e-mails de **Cloudflare Access**.

## Ton contenu

Remplace `panel/templates/home.html` et `panel/main.py` par tes écrans. Protège
chaque route avec `@login_required` (importé depuis `panel.auth`). Réutilise les
classes du thème (`fl-card`, `fl-title-serif`, `.btn`…).

## Déploiement

Comme le site-base : gunicorn + systemd + tunnel Cloudflare. Le service écoute en
`127.0.0.1` (invisible sur le LAN) et `cloudflared` l'expose. Voir la doc
déploiement du site-base.
