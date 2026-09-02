# Modèle en couches — base verrouillée + surcouche projet

> **v2.0.0.** Ce dépôt est organisé en **deux couches** : une **base** commune
> (login Cloudflare, thème, permissions, Paramètres…) qui se met à jour toute
> seule, et une **surcouche projet** où tu ajoutes tes écrans **sans jamais
> toucher à la base**.

## Structure

```
ton-projet/
├── base/                 ← LA BASE (verrouillée — ne jamais éditer)
│    ├── panel/…              login, thème, permissions, Paramètres, Cloudflare…
│    └── .base-version        version installée (ex. 2.0.0)
├── app/                  ← TON PROJET (tout ce que tu ajoutes)
│    ├── __init__.py          register(flask_app) : branche tes écrans
│    ├── routes.py            tes pages
│    ├── templates/           tes écrans (priment sur ceux de la base)
│    └── schema.sql           tes tables métier
├── run.py / wsgi.py      démarrage (assemble base/ + app/)
├── manage.py             commandes (setup, reset_admin, set_email, sync_base)
└── requirements.txt
```

Sans dossier `app/`, la base tourne seule (écran de démo). Un modèle prêt à
copier est fourni : **`app.example/`** → copie-le en `app/`.

## Créer un nouveau projet

```bash
cp -r app.example app          # ta surcouche de départ
# édite app/routes.py, app/templates/, app/schema.sql
python run.py                  # http://127.0.0.1:8000
```

## Comment la surcouche se branche (sans toucher la base)

La base (`base/panel/__init__.py`) détecte `app/` et :

| Prise | Ce que tu fournis |
|---|---|
| **Écrans** | `register(flask_app)` enregistre tes blueprints (dont l'accueil `/`). |
| **Templates** | `app/templates/` s'ajoute et **prime** sur ceux de la base. |
| **Tables** | `app/schema.sql` est exécuté en plus du schéma de la base. |
| **Accueil** | ton `/` remplace l'écran de démo ; la base retrouve l'accueil via `home_url()`. |

Tu réutilises tout de la base par simple import :

```python
from panel.auth import login_required, current_compte, is_super_admin
from panel.db import get_db
# {% extends "base.html" %}  → thème + Paramètres + bandeau d'impersonation
```

**Données par utilisateur** (site cloisonné) : filtre par `current_compte()["id"]`
(compte *effectif*, impersonation incluse). Nomme la colonne `compte_id` → la base
sait réattribuer/fusionner ces lignes (cf. `set_email`).

## Mettre à jour la base (sans toucher ton projet)

- **Depuis l'app** : Paramètres → **Couche base** → « Mettre à jour la base ».
- **En commande** : `python manage.py sync_base [--ref 2.1.0]`.

Ça télécharge la dernière version du site-base et remplace **uniquement**
`base/panel/` (+ `.base-version`). Ton `app/` n'est jamais touché.

> Config : `BASE_REPO_URL` (dépôt source, défaut SuperNon0/Site-base) et
> `BASE_REPO_REF` (version précise ; sinon la dernière version « couches »).

## Règle d'or

**Ne modifie JAMAIS `base/`.** Si la base doit évoluer, la modification se fait
dans le dépôt site-base (demande-la), une version est publiée, et chaque projet
clique « Mettre à jour la base ». Tout ton travail vit dans `app/`.

## Verrou : la base **ne peut pas** être modifiée (pas seulement « ne doit pas »)

Deux garde-fous, en plus de la règle ci-dessus :

- **CI GitHub** (`.github/workflows/protect-base.yml`) : tout push ou PR qui
  **modifie `base/`** dans un dépôt **projet** échoue. (Le dépôt source du
  site-base est exclu par son nom.)
- **Hook pre-commit** (`.githooks/pre-commit`) : bloque un commit local touchant
  `base/`. À activer une fois par projet :

  ```bash
  git config core.hooksPath .githooks
  ```

  Contournement volontaire (rare) : `ALLOW_BASE_EDIT=1 git commit …`.

Et rappel : `sync_base` **écrase** `base/` — toute modification locale y serait de
toute façon **effacée** à la prochaine mise à jour de la base.
