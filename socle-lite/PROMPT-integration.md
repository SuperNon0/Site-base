# Prompt d'intégration (à donner au dev IA)

Copie-colle le bloc ci-dessous à l'assistant qui travaille sur un projet
(BotPanel, FuelLog, …) pour lui donner **la même sécurité et la même interface**
que le reste de la flotte, **sans fusionner** avec le site-base.

> Source de vérité : la branche `claude/socle-lite` du dépôt
> `SuperNon0/Site-base` (dossier `socle-lite/`).

---

```text
CONTEXTE
Ce projet doit adopter la MÊME protection et la MÊME interface que mes autres
sites, sans embarquer tout le site-base. La référence (code testé) est ici :
https://github.com/SuperNon0/Site-base  branche claude/socle-lite  (dossier socle-lite/)
- Sécurité : dossier socle-lite/ports/  (RECETTE-cloudflare.md + ports/fastapi/)
- Interface : socle-lite/panel/static/ (thème) + socle-lite/panel/templates/ (gabarits)

TA MISSION — ajouter à CE projet, SANS casser ses fonctionnalités existantes :

1) TRAVAILLE SUR UNE BRANCHE DÉDIÉE, jamais sur main. Ne merge pas toi-même.

2) SÉCURITÉ — vérification du badge Cloudflare Access.
   - Récupère le module de référence testé :
     https://raw.githubusercontent.com/SuperNon0/Site-base/claude/socle-lite/socle-lite/ports/fastapi/cloudflare_access.py
     (si ce projet est en FastAPI/Python : réutilise-le presque tel quel ;
      sinon, PORTE-le en suivant socle-lite/ports/RECETTE-cloudflare.md — 4 étapes,
      même algo, seule la lib JWT change.)
   - Règles NON négociables : vérifier le JWT (RS256) + aud + iss ; ne JAMAIS faire
     confiance à l'en-tête Cf-Access-Authenticated-User-Email seul.
   - Garde le SECOURS LOCAL (mot de passe LAN) et la session existante du projet :
     ce module ne remplace QUE la lecture/vérif du badge Cloudflare.
   - Config attendue : CF_ACCESS_TEAM_DOMAIN, CF_ACCESS_AUD, CF_VERIFY_JWT (true en
     prod), ALLOW_LOCAL_LOGIN (false = entrée uniquement Cloudflare, accès direct → refusé).
   - EXCEPTION machine : les routes appelées par des machines (ex. /api/notify de
     BotPanel, webhooks Home Assistant) restent ACCESSIBLES sans badge — protège-les
     par une clé API / le LAN, jamais par le login humain.

3) INTERFACE — thème partagé (identique aux autres sites).
   - Copie TELS QUELS le thème : style.css, fonts.css, logo.svg depuis
     https://github.com/SuperNon0/Site-base/tree/claude/socle-lite/socle-lite/panel/static
     et sers-les dans le dossier statique du projet.
   - Reproduis la structure HTML avec les MÊMES classes (fl-card, fl-title-serif,
     .btn, .topbar, .login-card, .login-page…). Si le projet utilise Jinja2,
     réutilise les gabarits socle-lite/panel/templates/ (base.html, login.html,
     bloque.html) en adaptant url_for au framework.
   - N'invente pas de couleurs : passe par les variables :root du thème.
   - ⚠️ LA PAGE DE LOGIN DOIT ÊTRE IDENTIQUE SUR TOUS LES SITES. Reproduis
     socle-lite/panel/templates/login.html À L'IDENTIQUE : même structure HTML,
     mêmes classes, même disposition (logo + carte centrée). NE LA REDESSINE PAS.
     Adapte uniquement url_for au framework. Contenu : UN SEUL champ « mot de passe »,
     AUCUN identifiant / e-mail / nom d'utilisateur (l'identité vient de Cloudflare ;
     le mot de passe local n'est qu'un secours), + le lien « mot de passe oublié ».

AVANT DE DIRE QUE C'EST FINI
- La vérif Cloudflare rejette un en-tête forgé sans jeton (teste-le).
- ALLOW_LOCAL_LOGIN=false → un accès direct (sans badge) est refusé (403), même en POST.
- Les routes machine existantes (notif, webhooks) fonctionnent toujours.
- L'interface (login, pages) a le même rendu que les autres sites.

À ME LIVRER
- La branche poussée (SANS merge dans main).
- Un court résumé : où est branchée la vérif Cloudflare, ce qui a été repris du
  thème, et comment tester.
```

---

## Notes selon le projet
- **BotPanel** (FastAPI + Jinja2 + PyJWT) : réutilise directement
  `ports/fastapi/cloudflare_access.py` ; le thème et les gabarits Jinja2 se copient
  presque tels quels (juste `url_for` → Starlette). Voir `ports/fastapi/README.md`.
- **FuelLog** (autre techno) : suis `ports/RECETTE-cloudflare.md` pour la vérif
  (porte les 4 étapes dans la lib JWT du langage) ; le thème (CSS/HTML) se copie tel
  quel — c'est universel.
