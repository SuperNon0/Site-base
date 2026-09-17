# Recette universelle — vérifier un badge Cloudflare Access

Le **même algorithme** dans n'importe quel langage (Python, Node, Go, PHP…). Seule
la lib JWT change. C'est ça qu'on garde identique partout ; le reste (routes,
framework) est propre à chaque projet.

## Le contrat
On ne fait **jamais** confiance à l'en-tête `Cf-Access-Authenticated-User-Email`
seul (forgeable si l'origine est joignable hors Cloudflare). On **vérifie le jeton
signé**.

## Les étapes (identiques partout)
1. **Récupérer le jeton** : en-tête `Cf-Access-Jwt-Assertion`, sinon cookie `CF_Authorization`.
   Pas de jeton → **refusé**.
2. **Récupérer les clés publiques** de l'équipe (JWKS, mises en cache) :
   `https://<team>.cloudflareaccess.com/cdn-cgi/access/certs`
3. **Vérifier et décoder** le JWT :
   - algorithme **`RS256`**,
   - **`audience` = ton AUD** d'application Access,
   - **`issuer` = `https://<team>.cloudflareaccess.com`**.
   Échec (signature, expiration, aud/iss faux) → **refusé**.
4. **En tirer l'e-mail** : le claim `email` du jeton (en minuscules).

## Config nécessaire (les 3 mêmes valeurs partout)
- `team` : nom de l'équipe (ex. `super-nono`) — normalise : enlève `https://`, les
  `/` et `.cloudflareaccess.com`.
- `aud` : l'AUD de l'application Access.
- `verify` : `true` en prod ; `false` seulement en dev local (là on lit juste l'en-tête).

## Défense en profondeur (obligatoire)
- Rends l'origine **injoignable hors Cloudflare** (tunnel `cloudflared` ou pare-feu
  limité aux IP Cloudflare). La vérif JWT protège l'appli ; l'isolation réseau
  protège l'origine.
- **Secours local** (mot de passe LAN) pour ne pas te verrouiller dehors si
  Cloudflare tombe — désactivable.

## Implémentations de référence (testées)
| Stack | Fichier |
|---|---|
| **Flask** (Python) | `../panel/auth.py` (`cf_access_email`) — dans site-base aussi |
| **FastAPI / Starlette** (Python) | `fastapi/cloudflare_access.py` |
| Node / autre | à porter en suivant les 4 étapes ci-dessus |

## Pseudocode (à traduire dans ta lib JWT)
```
function cf_access_email(request, team, aud, verify):
    if not verify:
        return header(request, "Cf-Access-Authenticated-User-Email")  # dev only
    token = header(request, "Cf-Access-Jwt-Assertion") or cookie(request, "CF_Authorization")
    if not token: return null
    jwks = fetch_and_cache("https://{team}.cloudflareaccess.com/cdn-cgi/access/certs")
    try:
        claims = jwt_verify(token, jwks, alg="RS256", audience=aud,
                            issuer="https://{team}.cloudflareaccess.com")
    except: return null
    return lower(claims["email"])
```
