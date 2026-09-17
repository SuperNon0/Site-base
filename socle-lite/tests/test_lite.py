"""Smoke socle-lite."""
import os, sys, importlib
ROOT="/home/user/Site-base/socle-lite"
sys.path.insert(0, ROOT)
P=F=0
def ck(c,l):
    global P,F
    print(("  ok   " if c else "  FAIL ")+l); P+=c==True; F+=c!=True

def app_with(env):
    for m in list(sys.modules):
        if m=="panel" or m.startswith("panel."): del sys.modules[m]
    base=dict(SECRET_KEY="x"*40, CF_VERIFY_JWT="false", ALLOW_LOCAL_LOGIN="true",
              ADMIN_PASSWORD="pw", CF_ACCESS_TEAM_DOMAIN="", CF_ACCESS_AUD="",
              ALLOWED_EMAILS="", BRAND_PREFIX="Mon", BRAND_SUFFIX="Outil", BRAND_BADGE="app",
              SESSION_COOKIE_SECURE="false")
    base.update(env)
    for k,v in base.items(): os.environ[k]=v
    import panel
    a=panel.create_app(); a.config["TESTING"]=True
    return a

print("== 1. Redirection & login local ==")
a=app_with({}); c=a.test_client()
r=c.get("/"); ck(r.status_code in (301,302), "/ non connecté → redirection gateway")
r=c.get("/gateway"); ck(r.status_code==200 and "mot de passe" in r.get_data(as_text=True).lower(), "gateway (LAN) → page login")
r=c.post("/login", data={"password":"mauvais"})
with c.session_transaction() as s: ck("auth" not in s, "mauvais mot de passe → pas connecté")
r=c.post("/login", data={"password":"pw"})
with c.session_transaction() as s: ck(s.get("auth")==True, "bon mot de passe → connecté")
r=c.get("/"); ck(r.status_code==200 and "Authentifié" in r.get_data(as_text=True), "accueil protégé → 200")
c.get("/logout")
with c.session_transaction() as s: ck("auth" not in s, "logout → session vidée")

print("\n== 2. Login local désactivé → Cloudflare uniquement ==")
a=app_with({"ALLOW_LOCAL_LOGIN":"false"}); c=a.test_client()
r=c.get("/gateway"); ck(r.status_code==403, "gateway LAN → 403 (accès refusé)")
r=c.post("/login", data={"password":"pw"})
with c.session_transaction() as s: ck("auth" not in s and r.status_code==403, "POST direct → refusé (403), pas de bypass")

print("\n== 3. Entrée Cloudflare (badge) ==")
a=app_with({}); c=a.test_client()
r=c.get("/gateway", headers={"Cf-Access-Authenticated-User-Email":"noe@x.fr"})
with c.session_transaction() as s: ck(s.get("auth")==True and s.get("email")=="noe@x.fr", "e-mail Cloudflare → connecté")

print("\n== 4. Restriction ALLOWED_EMAILS ==")
a=app_with({"ALLOWED_EMAILS":"admin@x.fr"}); c=a.test_client()
r=c.get("/gateway", headers={"Cf-Access-Authenticated-User-Email":"intrus@x.fr"})
with c.session_transaction() as s: ck("auth" not in s and r.status_code==403, "e-mail hors liste → 403")
c2=a.test_client()
r=c2.get("/gateway", headers={"Cf-Access-Authenticated-User-Email":"admin@x.fr"})
with c2.session_transaction() as s: ck(s.get("auth")==True, "e-mail autorisé → connecté")

print("\n== 5. /api → no-store ==")
a=app_with({}); c=a.test_client()
# route /api inexistante mais le after_request s'applique à tout /api/*
r=c.get("/api/whatever"); ck(r.headers.get("Cache-Control")=="no-store", "/api/* → Cache-Control no-store")

print(f"\n=== socle-lite : {P} ok, {F} échec(s) ===")
sys.exit(1 if F else 0)
