# socle-lite — sécurité + interface partagées (sans comptes)

Branche **`claude/socle-lite`**. Objectif : donner à **tous tes petits outils sans
comptes** la **même protection** (vérification Cloudflare, testée) et la **même
interface** (thème), **quel que soit le langage**, sans embarquer tout le site-base.

> Pour un site **multi-utilisateurs** (comptes, rôles, validation, impersonation)
> → utilise le **site-base complet** (`main`), pas ce socle-lite.

---

## Ce que contient cette branche

```
socle-lite/
├── panel/                     ← appli Flask minimale, PRÊTE À L'EMPLOI
│   ├── __init__.py            fabrique (auth + accueil + no-store /api)
│   ├── config.py             config .env (aucune base de données)
│   ├── auth.py               Cloudflare Access + secours local (repris du site-base, testé)
│   ├── main.py               accueil de démo (à remplacer par ton outil)
│   ├── templates/            base.html, login.html, bloque.html, home.html (thème)
│   └── static/               style.css, fonts.css, logo.svg (LE thème)
├── ports/                     ← pour les autres langages/frameworks
│   ├── RECETTE-cloudflare.md  la vérif Cloudflare en 4 étapes (langage-agnostique)
│   └── fastapi/               port FastAPI (pour BotPanel) : cloudflare_access.py + README
├── tests/test_lite.py         12 vérifs (login local, désactivation étanche, Cloudflare, allowlist)
├── run.py / wsgi.py           dev / prod (gunicorn)
├── requirements.txt · .env.example
└── README.md                  (ce fichier)
```

## Ce que le socle-lite fournit (et RIEN d'autre)
- ✅ **Vérification Cloudflare Access** (JWT `RS256` + `aud` + `iss`) — **reprise à
  l'identique du site-base**, testée. Jamais de confiance à l'en-tête seul.
- ✅ **Secours local** (mot de passe LAN), **désactivable et étanche** (POST direct refusé).
- ✅ **Un seul statut** : authentifié ou refusé. **Zéro compte, zéro rôle, zéro page Paramètres.**
- ✅ **Le thème** (même look que tes autres sites).

## Les 3 couches, et ce qui se partage
| Couche | Partage entre langages |
|---|---|
| **Interface** (CSS, logo, classes HTML) | ✅✅ copie **telle quelle**, identique partout |
| **Sécurité** (vérif Cloudflare) | ✅ même algo, ~30 lignes à porter par langage (voir `ports/`) |
| **Colle du framework** (routes, moteur de templates) | ❌ propre à chaque projet |

---

## Utiliser le socle-lite

### A. Nouveau site en **Flask** (le plus direct)
Copie `socle-lite/` comme point de départ :
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # SECRET_KEY + (option) ADMIN_PASSWORD + Cloudflare
python run.py             # http://127.0.0.1:8000
```
Puis remplace `panel/main.py` + `panel/templates/home.html` par ton outil, en
protégeant tes routes avec `@login_required` (depuis `panel.auth`).

### B. Site en **FastAPI** (ex. BotPanel)
Voir [`ports/fastapi/README.md`](ports/fastapi/README.md) :
- copie `ports/fastapi/cloudflare_access.py` (la vérif) ;
- copie le **thème** (`panel/static/*`) et réutilise les **gabarits Jinja2** (`panel/templates/*`) ;
- adapte `url_for` → Starlette.

### C. Site dans **un autre langage** (ex. FuelLog)
Suis [`ports/RECETTE-cloudflare.md`](ports/RECETTE-cloudflare.md) (les 4 étapes,
identiques partout) et **copie le thème tel quel** (CSS/HTML universels).

---

## Réglages clés (`.env`)
| Variable | Effet |
|---|---|
| `CF_ACCESS_TEAM_DOMAIN` / `CF_ACCESS_AUD` | ta config Cloudflare Access |
| `CF_VERIFY_JWT` | `true` en prod (vérifie le badge), `false` en dev |
| `ALLOW_LOCAL_LOGIN=false` | **entrée uniquement par Cloudflare** (accès direct → 403) |
| `ADMIN_PASSWORD` | mot de passe de secours LAN (vide = pas de login local) |
| `ALLOWED_EMAILS` | (option) restreindre aussi côté appli ; vide = on fait confiance à Cloudflare |

## Réinitialiser le mot de passe de secours local
Le mot de passe local n'est pas en base : c'est `ADMIN_PASSWORD` dans le `.env`.
Un script le change et recharge le service :
```bash
sudo bash deploy/reset-password.sh                 # génère un mot de passe et l'affiche
sudo bash deploy/reset-password.sh 'MonNouveauMdp' # fixe un mot de passe précis
```
(Réglages si ton install diffère : `INSTALL_DIR=`, `SERVICE=`, `ENV_FILE=`.)

## Tests
```bash
python socle-lite/tests/test_lite.py                        # 12 vérifs (Flask)
python socle-lite/ports/fastapi/test_cloudflare_access.py    # module FastAPI
```

## Intégrer sur un projet existant (dev IA)
Un prompt prêt à copier-coller est fourni : [`PROMPT-integration.md`](PROMPT-integration.md).
