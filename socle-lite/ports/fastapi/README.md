# Port FastAPI — Cloudflare Access + thème partagé (pour BotPanel)

BotPanel est **Python + FastAPI + Jinja2 + PyJWT** → tout se partage facilement.

## 1. La vérif Cloudflare (le morceau sécurité)
Copie `cloudflare_access.py` dans BotPanel. Il reprend **à l'identique** la logique
testée du site-base. Branche-le sur ta route d'entrée :

```python
from cloudflare_access import cf_access_email

@app.get("/gateway")
async def gateway(request: Request):
    email = cf_access_email(request, team=CF_TEAM, aud=CF_AUD, verify=CF_VERIFY)
    if email is not None:
        # (option) vérifie que l'e-mail est dans ta liste autorisée
        request.session["email"] = email      # ta session signée existante
        return RedirectResponse("/", status_code=302)
    # pas de badge → login local (secours LAN) ou refus, selon ta config
    ...
```

- Tu **as déjà** `PyJWT[crypto]` → aucune dépendance à ajouter.
- Garde ton **secours local** (mot de passe) et ta **session signée** actuels : ce
  module ne remplace **que** la lecture/vérif du badge Cloudflare.
- `ALLOW_LOCAL_LOGIN=false` → n'affiche pas de login et **refuse** l'accès direct.

## 2. Le thème (le look identique)
Le look est **du CSS + du HTML**, donc **rien à porter** :

- **Copie les 3 fichiers** depuis `../panel/static/` : `style.css`, `fonts.css`,
  `logo.svg` → dans le dossier statique de BotPanel. Sers-les tels quels.
- **Réutilise les gabarits Jinja2** de `../panel/templates/` (`base.html`,
  `login.html`, `bloque.html`, `home.html`). BotPanel utilise **déjà Jinja2**.
  Seule adaptation : `url_for(...)` de Flask → l'équivalent Starlette
  (`request.url_for(...)`), et sers le statique via `app.mount("/static", ...)`.
- Garde **les mêmes classes** (`fl-card`, `fl-title-serif`, `.btn`, `.topbar`,
  `.login-card`…) → rendu **identique** aux autres sites, sans réinventer le style.

## Résultat
BotPanel obtient **la même sécurité** (vérif Cloudflare testée) et **la même
interface** (thème partagé) que tes autres sites — en restant en FastAPI, sans
fusionner avec le site-base.

> Pour porter vers **un autre langage** (ex. FuelLog), suis
> [`../RECETTE-cloudflare.md`](../RECETTE-cloudflare.md) : les 4 étapes sont les
> mêmes, seule la lib JWT change. Le thème (CSS/HTML) se copie tel quel.
