# Permissions — demandées à la création de chaque site

Chaque site créé depuis le socle **choisit ses permissions**. Une permission
(*capability*) répond à la question « qui a le droit de faire ça ? » avec trois
niveaux :

| Niveau | Qui |
|---|---|
| `off` | personne (fonctionnalité **désactivée** sur ce site) |
| `membre` | tout compte **actif** (membre ou super-admin) |
| `super_admin` | **super-admin** uniquement |

> ⚠️ **À la création d'un site, il faut demander au propriétaire le niveau de
> CHAQUE permission** (voir `CLAUDE.md`). L'assistant `python -m panel.setup` pose
> les questions et remplit `.env`.

## Les permissions

| Clé (`.env`) | Fonctionnalité | Défaut |
|---|---|---|
| `CAP_ACCOUNT_MANAGEMENT` | Gestion des comptes : demandes d'accès, validation, refus, **blocage**, suppression, rôles. | `super_admin` |
| `CAP_PROFILES` | Voir les profils du site + **« se mettre à leur place »** (impersonation) pour consulter/éditer leurs données. | `super_admin` |
| `CAP_ADMIN_PASSWORD` | Changer le **mot de passe administrateur** dans les Paramètres. | `super_admin` |
| `CAP_SITE_UPDATE` | Bouton **« Mettre à jour le site »** (git + pip + redémarrage) et `/api/system/*`. | `super_admin` |

### Cas particulier : `CAP_ACCOUNT_MANAGEMENT`

Cette permission pilote aussi le **modèle d'accès** du site :

- **≠ `off` (ex. `super_admin`)** → site **« géré » (hub)** : un e-mail inconnu
  passe par *demande → validation → actif*, avec blocage/suppression possibles.
- **`off`** → site **« perso »** : Cloudflare a déjà filtré qui entre, donc
  l'utilisateur est **créé automatiquement en `actif`** à sa 1re visite. Pas de
  validation ni de blocage en local — ça se gère **au hub**. L'écran « Comptes »
  devient un écran **« Profils »** (voir + impersonation, selon `CAP_PROFILES`).

## Presets

`python -m panel.setup --preset <nom>` :

| Preset | account_management | profiles | admin_password | site_update |
|---|---|---|---|---|
| `hub` (la home page) | super_admin | super_admin | super_admin | super_admin |
| `perso` (site applicatif) | **off** | super_admin | super_admin | **off** |

## Exemples

**Site bibliothèque de films** (accès géré au hub, tu vois et édites les listes
des membres, pas de bouton mise à jour) :

```env
CAP_ACCOUNT_MANAGEMENT=off
CAP_PROFILES=super_admin
CAP_ADMIN_PASSWORD=super_admin
CAP_SITE_UPDATE=off
```

**La home page (hub)** : tout en `super_admin` (preset `hub`).

## Qui est super-admin ? (défini une fois, appliqué partout)

Le rôle `super_admin` est stocké **par site**, mais tu n'as pas à le régler site
par site : une **liste partagée** d'e-mails, la même sur tous les sites, suffit.

```env
# La MÊME valeur sur chaque site (idéalement posée par le déploiement)
SUPERADMIN_EMAILS=toi@gmail.com, autre-admin@gmail.com
```

À chaque connexion, tout e-mail de cette liste est **automatiquement élevé en
`super_admin` actif** sur le site courant :

- sur un **site perso**, il devient super-admin au lieu de simple membre ;
- sur un **hub**, il entre directement (pas de « demander un accès ») ;
- un membre existant ajouté à la liste est **promu** à sa prochaine connexion ;
- un super-admin désigné **ne peut pas être bloqué** localement (il est ré-activé).

> C'est la réponse à « je définis mes super-admins au même endroit et ça
> s'applique partout » : tu maintiens **une seule liste**, déployée à l'identique.
> (`SUPERADMIN_EMAIL` + `SUPERADMIN_PASSWORD` restent, eux, pour le **login local
> LAN** par mot de passe.)
>
> Variante entièrement dynamique (ajouter/retirer un super-admin depuis l'UI du
> hub, sans redéployer) : possible en faisant interroger le hub par les sites —
> non implémenté ici, à demander si besoin.

## Dans le code

- `panel/permissions.py` — registre des capabilities, `capability_level()`,
  `has_capability()`, décorateur `require_capability()`, `access_managed()`.
- Les routes sont protégées par `@require_capability("…")` (403 JSON sur `/api/*`,
  sinon redirection).
- Les templates masquent les boutons via `{% if can('…') %}` (helper injecté).
- Ajouter une permission = une entrée dans `CAPABILITIES`, une variable
  `CAP_*` dans `config.py`/`.env.example`, et les gardes correspondantes.
