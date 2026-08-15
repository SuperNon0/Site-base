# SSO — un seul login pour tous tes sites (hub + clients)

Objectif : **te connecter une seule fois** sur un site central (le **hub**, ta
home page) et accéder ensuite à **tous tes autres sites** sans te reconnecter.

Ce document décrit le mode SSO intégré au site de base. Il est **optionnel** :
par défaut (`AUTH_MODE=standalone`) le site garde le comportement v1.0.0
(Cloudflare Access + login local). Le SSO s'active par configuration, sans rien
changer d'autre.

---

## 1. Décisions retenues

| Décision | Choix |
|---|---|
| Répartition des sites | **Sous-domaines d'un même domaine** (ex. `hub.super-nono.cc`, `app1.super-nono.cc`) |
| Authentification de base | **Cloudflare Access / Google**, une seule fois, **sur le hub** |
| Comptes & rôles | **Identité centrale, accès géré par site** |

**« Identité centrale, accès par site »** = le hub prouve *qui tu es* (un seul
login). Chaque site garde **son propre** contrôle d'accès : un même e-mail peut
être `actif`/super-admin sur un site, `pending` ou `bloqué` sur un autre. On
réutilise donc tel quel le système de comptes du site de base.

---

## 2. Principe (cookie de session partagé)

Comme tous les sites sont des **sous-domaines d'un même domaine**, on utilise un
**cookie signé posé sur le domaine parent** (`.super-nono.cc`), lisible par tous
les sous-domaines.

```
1. L'utilisateur ouvre  app1.super-nono.cc  (client)
2. Pas de cookie SSO → app1 le redirige vers  hub.super-nono.cc/sso/login?next=app1…
3. Le hub est derrière Cloudflare Access : Google login (si pas déjà fait),
   puis Cloudflare transmet l'e-mail vérifié au hub.
4. Le hub pose un cookie « sso_session » signé (JWT HS256) sur .super-nono.cc
   et redirige vers app1.
5. app1 lit le cookie, vérifie la signature avec le SECRET PARTAGÉ, obtient
   l'e-mail, puis applique SON contrôle d'accès (pending/actif/bloqué + rôles).
6. app2, app3… : le cookie est déjà là → accès direct, plus aucun login.
```

Le cookie ne contient que l'**e-mail vérifié** + une **expiration**, signés. Il
ne porte aucun rôle : chaque site décide des droits de son côté.

---

## 3. Configuration

Mêmes variables partout, **`SSO_SECRET` identique** sur le hub et tous les
clients (c'est lui qui lie les sites entre eux).

### Le hub (ta home page)

```env
AUTH_MODE=hub
SSO_SECRET=<le même secret partout>          # python -c "import secrets; print(secrets.token_hex(32))"
SSO_COOKIE_DOMAIN=.super-nono.cc
SSO_COOKIE_NAME=sso_session
SESSION_COOKIE_SECURE=true
# Cloudflare Access sur le hub (comme en mode standalone) :
CF_ACCESS_TEAM_DOMAIN=<ton-equipe>
CF_ACCESS_AUD=<aud-du-hub>
CF_VERIFY_JWT=true
```

### Chaque autre site (client)

```env
AUTH_MODE=sso_client
SSO_SECRET=<le même secret que le hub>
SSO_COOKIE_DOMAIN=.super-nono.cc
SSO_COOKIE_NAME=sso_session
SSO_HUB_URL=https://hub.super-nono.cc        # où rediriger pour se connecter
SESSION_COOKIE_SECURE=true
```

> Un client **n'a pas besoin** de Cloudflare Access ni de login local : il fait
> confiance au cookie signé par le hub. Garde quand même son origine joignable
> **uniquement via Cloudflare** (tunnel `cloudflared`), et le cookie en HTTPS.

---

## 4. Ce qui change dans le code (et ce qui ne change pas)

Seule l'**étape « prouver qui tu es »** change ; tout le reste est identique.

| Élément | standalone | hub | sso_client |
|---|---|---|---|
| Source de l'e-mail | Cloudflare (en-tête + JWT) | Cloudflare | **cookie SSO** |
| Si pas d'e-mail | login local (LAN) | login local (LAN) | **redirige vers le hub** |
| Émet le cookie partagé | — | **oui** (`/sso/login`) | — |
| Cycle de vie comptes | ✅ | ✅ | ✅ (inchangé) |
| Rôles / impersonation | ✅ | ✅ | ✅ (inchangé) |

Implémentation :
- `panel/sso.py` — signe/vérifie le cookie (JWT HS256), pose/purge le cookie,
  garde-fou anti open-redirect (`is_safe_next`).
- `panel/auth.py` — `effective_email()` : cookie SSO en mode client, sinon
  Cloudflare.
- `panel/routes/sso_routes.py` — `/sso/login` et `/sso/logout` (actifs sur le hub).
- `panel/routes/auth_routes.py` — le `gateway` redirige vers le hub en mode client ;
  la déconnexion d'un client purge le cookie global via le hub.

---

## 5. Déconnexion

- **Client** : `/logout` vide la session locale **et** redirige vers
  `{hub}/sso/logout` pour purger le cookie partagé (déconnexion de partout).
- **Hub** : `/sso/logout` supprime le cookie du domaine parent.

---

## 6. Sécurité

- `SSO_SECRET` : long, aléatoire, **jamais** commité (dans `.env`). Le changer
  invalide toutes les sessions SSO.
- Cookie : `HttpOnly`, `Secure` (HTTPS), `SameSite=Lax`, sur le domaine parent.
- Jeton : signé HS256, **expiration** obligatoire (`SSO_TTL`, 12 h par défaut).
- Anti open-redirect : le hub ne redirige `next` que vers un hôte du domaine
  autorisé (`SSO_COOKIE_DOMAIN`).
- Chaque site garde son contrôle d'accès : un utilisateur `bloqué` sur un site
  n'y entre pas, même avec un cookie SSO valide.
- Le hub reste protégé par Cloudflare Access (c'est lui qui fait le vrai login
  Google).

---

## 7. Brancher un nouveau site sur le SSO

1. Déploie le site-base normalement (voir `deploiement-proxmox.md`).
2. Mets dans son `.env` : `AUTH_MODE=sso_client`, le **même** `SSO_SECRET`, le
   `SSO_COOKIE_DOMAIN` et `SSO_HUB_URL`.
3. Sers-le sur un **sous-domaine** du même domaine parent.
4. C'est tout : le premier accès redirige vers le hub, puis l'utilisateur revient
   authentifié. S'il est inconnu du site, il tombe sur « Demander un accès » (que
   le super-admin du site valide) — le contrôle d'accès reste par site.
