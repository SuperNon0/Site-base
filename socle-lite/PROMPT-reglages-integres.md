# Prompt — réglages intégrés (Cloudflare + mot de passe) dans un site

À donner au dev IA d'un site (BotPanel, FuelLog…) qui veut son **propre écran de
réglages**, natif à sa DA, branché sur la vérification Cloudflare testée du socle.

> Référence : dépôt `SuperNon0/Site-base`, branche `claude/socle-lite`, dossier
> `socle-lite/` (noyau de sécurité `ports/`, thème `panel/static` + `panel/templates`).

---

```text
CONTEXTE
Je veux, DANS CE SITE, un écran de réglages qui fait partie du site (sa propre
navigation, sa DA), PAS un panneau générique posé par-dessus. Il gère la config
Cloudflare (équipe + AUD) et le mot de passe de secours local. La sécurité doit
réutiliser le noyau testé du socle, jamais être réinventée.
Référence : https://github.com/SuperNon0/Site-base  branche claude/socle-lite
- Sécurité : socle-lite/ports/ (RECETTE-cloudflare.md + ports/fastapi/cloudflare_access.py)
- Thème : socle-lite/panel/static/ + socle-lite/panel/templates/

TA MISSION — SANS casser l'existant :

1) BRANCHE DÉDIÉE, jamais main. Ne merge pas toi-même.

2) NOYAU DE SÉCURITÉ (réutilisé, pas réécrit)
   - Utilise la vérification du badge Cloudflare du socle : dans ce langage,
     réutilise ports/fastapi/cloudflare_access.py (FastAPI) OU porte les 4 étapes de
     RECETTE-cloudflare.md (autre stack). Vérifie JWT (RS256) + aud + iss ; ne fais
     JAMAIS confiance à l'en-tête Cf-Access-Authenticated-User-Email seul.
   - La fonction prend team/aud/verify EN PARAMÈTRES : passe-lui les valeurs que le
     site a stockées (voir 3), pour que la config soit modifiable au runtime.

3) STOCKAGE DES RÉGLAGES (dans le store du site, pas un .env figé)
   - Stocke dans la base/le store du site : cf_team, cf_aud, cf_verify, et le
     mot de passe local (HASHÉ : PBKDF2/bcrypt/argon2 — jamais en clair).
   - Au démarrage, si le store est vide, initialise depuis les variables
     d'environnement (CF_ACCESS_TEAM_DOMAIN, CF_ACCESS_AUD, CF_VERIFY_JWT, ADMIN_PASSWORD)
     pour la première install.

4) ÉCRAN DE RÉGLAGES (intégré à la DA du site, protégé par login)
   - Accessible UNIQUEMENT authentifié (sinon redirection/refus).
   - Champs : équipe Cloudflare, AUD, vérif on/off ; bouton « Tester » qui tente la
     vérif avec les valeurs saisies et affiche le résultat (jeton reçu ? en-tête
     e-mail ? JWT OK/échec + détail) — SANS enregistrer tant que non validé.
   - Bloc « mot de passe » : changer le mot de passe local (formulaire authentifié →
     écrit le nouveau HASH).
   - Utilise les classes du thème partagé (fl-card, fl-title-serif, .btn, .topbar…)
     pour que l'écran ait le même look que mes autres sites, tout en vivant dans la
     navigation du site.

5) « MOT DE PASSE OUBLIÉ » (sur le login) — SÛR
   - Le lien n'effectue AUCUN reset depuis le web (sinon n'importe qui pourrait
     réinitialiser). Il indique la commande serveur, et tu fournis un petit script
     serveur (ex. reset-password.sh) qui régénère le hash dans le store + recharge.

6) RÈGLES CONSERVÉES
   - Secours local (mot de passe LAN) gardé ; ALLOW_LOCAL_LOGIN=false → entrée
     uniquement Cloudflare, accès direct refusé (403), même en POST.
   - Routes machine (ex. /api/notify, webhooks Home Assistant) restent accessibles
     sans badge → protège-les par clé API / LAN, jamais par le login humain.
   - Anti-verrouillage : si on change la config Cloudflare et qu'elle devient
     fausse, le secours local doit rester utilisable.

AVANT DE DIRE QUE C'EST FINI
- Un en-tête Cloudflare forgé sans jeton valide est rejeté (teste-le).
- Le bouton « Tester » distingue bien OK / échec.
- Changer le mot de passe fonctionne (nouveau hash, ancien refusé).
- ALLOW_LOCAL_LOGIN=false → accès direct sans badge = 403 (même en POST).
- Les routes machine marchent toujours.
- L'écran de réglages a le même rendu (thème) que mes autres sites.

À ME LIVRER
- La branche poussée (SANS merge dans main).
- Résumé : où est branchée la vérif Cloudflare, où sont stockés les réglages,
  comment tester, et la commande de reset serveur.
```

---

## Rappels
- **BotPanel** (FastAPI/Jinja2/PyJWT) : réutilise `ports/fastapi/cloudflare_access.py`
  presque tel quel ; l'écran de réglages se fait en Jinja2 avec le thème.
- **FuelLog** (autre techno) : porte la vérif via `RECETTE-cloudflare.md` ; le thème
  (CSS/HTML) se copie tel quel.
- **Point de vigilance** : la vérif Cloudflare est *réutilisée du socle* (testée) ;
  seuls le **stockage** et l'**écran** sont propres au site.
