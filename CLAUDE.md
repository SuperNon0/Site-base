# CLAUDE.md — instructions pour le développeur (IA)

> Ce fichier est lu en premier par l'assistant qui reprend ce dépôt. Il fixe le
> **contrat** : ce qui doit être reproduit **à l'identique**, et ce qui est libre.
>
> 📖 Pour **comprendre le code** (architecture, rôle de chaque fichier, pourquoi
> chaque choix, et comment étendre le socle), lis
> [`docs/guide-developpeur.md`](docs/guide-developpeur.md).

## 1. Ce qu'est ce dépôt

Un **site de base** (template de fondation) réutilisé pour démarrer chaque
nouveau projet. Il fournit, prêts à l'emploi :

1. **Le thème visuel « RecipeLog »** (dark + accent doré) — voir
   [`docs/theme-recipelog.md`](docs/theme-recipelog.md), implémenté dans
   [`panel/static/style.css`](panel/static/style.css) + [`fonts.css`](panel/static/fonts.css).
2. **L'authentification v2 multi-comptes** derrière **Cloudflare Zero Trust** —
   spec [`docs/authentification-v2.md`](docs/authentification-v2.md), maquettes de
   référence [`docs/maquettes-auth-v2/`](docs/maquettes-auth-v2/).
3. **Les notifications via BotPanel** — [`docs/notifications-botpanel.md`](docs/notifications-botpanel.md),
   helper [`panel/notify.py`](panel/notify.py).
4. **Le déploiement Proxmox (LXC/VM) + Cloudflare** —
   [`docs/deploiement-proxmox.md`](docs/deploiement-proxmox.md).
5. **Le versionnage & les mises à jour** (tags `vX.Y.Z`, bouton « Mettre à jour ») —
   [`docs/versions.md`](docs/versions.md).
6. **Les permissions par site** (capabilities demandées à la création :
   `super_admin` / `membre` / `off`) — [`docs/permissions.md`](docs/permissions.md).
7. **La config Cloudflare éditable dans l'UI + un écran Diagnostic**
   (Paramètres → « Cloudflare / Accès » et « Diagnostic »), réglages stockés en
   base (`app_settings`, prioritaires sur `.env`) — voir `panel/settings.py`.

### Toute la documentation (à lire selon le besoin)

| Fichier | Pour quoi |
|---|---|
| [`docs/guide-developpeur.md`](docs/guide-developpeur.md) | **Comprendre le code** : architecture, rôle de chaque fichier, *pourquoi*, recettes d'extension. |
| [`docs/authentification-v2.md`](docs/authentification-v2.md) | Spec fonctionnelle de l'auth (états, rôles, sécurité §9). |
| [`docs/theme-recipelog.md`](docs/theme-recipelog.md) | Cahier des charges du thème (tokens, classes `fl-*`). |
| [`docs/permissions.md`](docs/permissions.md) | Permissions par site + super-admins + hub vs perso. |
| [`docs/notifications-botpanel.md`](docs/notifications-botpanel.md) | Intégration BotPanel. |
| [`docs/deploiement-proxmox.md`](docs/deploiement-proxmox.md) | Déploiement LXC/VM + Cloudflare + mise à jour. |
| [`docs/versions.md`](docs/versions.md) | Versionnage (tags `vX.Y.Z`) & rollback. |
| [`docs/mobile-anti-zoom.md`](docs/mobile-anti-zoom.md) | Comportement « app native » mobile. |
| [`CHANGELOG.md`](CHANGELOG.md) | Historique des versions. |

### Deux profils de site (choisis par les permissions)

- **Hub** (ta home page, données **partagées**) : `CAP_ACCOUNT_MANAGEMENT=super_admin`
  (gestion des comptes : demande → validation → blocage), `CAP_PROFILES=off`
  (impersonation inutile). Preset : `python -m panel.setup --preset hub`.
- **Site perso** (appli à données **cloisonnées** : films, suivi… ) :
  `CAP_ACCOUNT_MANAGEMENT=off` (l'utilisateur filtré par Cloudflare est créé
  **auto en actif**), `CAP_PROFILES=super_admin` (voir les profils + « se mettre à
  leur place »). Preset : `python -m panel.setup --preset perso`.

## 2. Règles de reproduction (NE PAS DÉVIER)

- **Le thème est un contrat visuel.** Les couleurs, polices, rayons et classes de
  `panel/static/style.css` doivent rester **identiques**. Le rendu doit
  correspondre aux captures de `docs/maquettes-auth-v2/captures/`. N'invente pas
  de nouvelles couleurs : passe **toujours** par les variables `:root`.
- **Les écrans d'auth** (`login`, `demande`, `attente`, `refus`, `bloque`,
  `comptes`, bandeau d'impersonation) doivent rester **fidèles aux maquettes**
  (structure HTML + classes). Les templates correspondants sont dans
  `panel/templates/`.
- **La sécurité de l'auth** (vérification du JWT Cloudflare + `aud`, dernier
  super-admin indestructible, sessions `compte_id`+`role`, `/api/*` en
  `no-store`, anti-force-brute) ne doit pas être affaiblie (spec §9).
- **Les notifications passent par BotPanel** (`panel/notify.py`), jamais en
  appelant Discord directement.
- **Comportement « app native » sur mobile** (anti-zoom) : garder le viewport
  `maximum-scale=1.0, user-scalable=no` (dans `base.html`), les champs à `16px`
  minimum et `touch-action: manipulation` sur `body`. Voir
  [`docs/mobile-anti-zoom.md`](docs/mobile-anti-zoom.md).

## 3. Ce que TU personnalises pour un projet

- **⚠️ Les permissions — À DEMANDER au propriétaire à la création du site.** Pour
  **chaque** permission, demande son niveau (`super_admin` / `membre` / `off`) :
  gestion des comptes, profils + « se mettre à leur place », changer le mot de
  passe admin, bouton « Mettre à jour le site ». Renseigne les `CAP_*` dans `.env`
  (ou lance `python -m panel.setup`). Voir [`docs/permissions.md`](docs/permissions.md).
  Rappel : `CAP_ACCOUNT_MANAGEMENT=off` → site « perso » (accès auto en actif,
  gestion des comptes au hub). `CAP_PROFILES` (« voir en tant que ») **uniquement
  sur les sites à données cloisonnées** ; `off` sur un site à données partagées
  (le hub).
- **Les super-admins** se désignent depuis **Paramètres → Super-admins**, et
  **seul le compte administrateur de base** (login local par mot de passe) peut le
  faire ; un super-admin « e-mail » ne le peut pas.
- **La marque** via `.env` : `BRAND_PREFIX`, `BRAND_SUFFIX`, `BRAND_BADGE`, et le
  logo `panel/static/logo.svg` (garde le viewBox 44×44).
- **Le contenu applicatif** : remplace `panel/templates/dashboard.html` et
  `panel/routes/main.py` par les écrans de ton projet, en réutilisant les classes
  du thème (`fl-card`, `fl-title-serif`, `.btn`, etc.).
- **Le modèle de données métier** : ajoute tes tables. ⚠️ **Décision bloquante**
  avant de coder du contenu multi-utilisateurs : bibliothèque **partagée** ou
  **cloisonnée** par compte ? Voir `authentification-v2.md` §7. À **poser au
  propriétaire du projet**.

## 4. Rôles (ce template)

Deux rôles seulement : `super_admin` (toi — gère tout, login local) et `membre`.
Le rôle `admin` intermédiaire de la spec n'est **pas** activé ici (simplification
assumée). Ne le réintroduis que si le propriétaire le demande explicitement.

## 5. Lancer en local

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # puis renseigne SECRET_KEY + SUPERADMIN_PASSWORD
python -m panel.setup       # (optionnel) pose chaque permission et remplit .env
python run.py               # http://127.0.0.1:8000
```

En dev sans Cloudflare : `CF_VERIFY_JWT=false` + `ALLOW_LOCAL_LOGIN=true`, et
connecte-toi en local avec `SUPERADMIN_PASSWORD`.

## 6. Structure

```
panel/
  __init__.py         app factory (blueprints, contexte, no-store)
  config.py           config depuis .env
  db.py               SQLite : schéma `comptes` + `audit`, amorce super-admin
  auth.py             Cloudflare Access (JWT + diagnostic), session, décorateurs
  settings.py         réglages en base (app_settings) : cf_config() prioritaire sur .env
  permissions.py      capabilities par site (off/membre/super_admin) + require_capability
  setup.py            assistant : demande chaque permission, écrit .env (python -m panel.setup)
  notify.py           helper BotPanel notify(slug, **vars)
  reset_admin.py      CLI de réinitialisation du mdp super-admin (python -m panel.reset_admin)
  utils.py            format date FR
  routes/
    auth_routes.py    gateway, login local, demande d'accès, mot de passe oublié, logout
    accounts_routes.py gestion comptes + impersonation + Paramètres/mdp (spec §5/§6/§8)
    system_routes.py  /api/system/* : bouton « Mettre à jour » (git+pip+SIGHUP)
    main.py           écran applicatif (à remplacer)
  templates/          base + écrans d'auth + parametres + oubli + dashboard
  static/             style.css (thème), fonts.css, logo.svg
docs/                 guide dev, spec auth, thème, permissions, notifications,
                      déploiement, versions, mobile, maquettes
deploy/               install_lxc.sh, site-base.service, update.sh, reset_admin.sh
run.py / wsgi.py      entrées dev / prod (gunicorn)
```

## 7. Vérifier avant de livrer

- [ ] Le rendu des écrans d'auth correspond aux captures de référence.
- [ ] Login local (LAN) ET parcours Cloudflare (demande→attente→validation) OK.
- [ ] `/api/*` renvoie `Cache-Control: no-store`.
- [ ] `CF_VERIFY_JWT=true` et `SESSION_COOKIE_SECURE=true` en production.
- [ ] Notifications BotPanel branchées sur les bons slugs.
- [ ] Permissions demandées au propriétaire et renseignées (`CAP_*` / `panel.setup`).
- [ ] `GET /login` redirige (pas de 405) ; `Paramètres → Diagnostic` affiche `OK ✓`
      derrière Cloudflare.
- [ ] Bouton « Mettre à jour » : recharge le service (SIGHUP gunicorn), sans sudo.
