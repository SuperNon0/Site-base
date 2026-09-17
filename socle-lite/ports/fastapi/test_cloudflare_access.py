"""Smoke du port FastAPI (chemin sans jeton + normalisation)."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import cloudflare_access as ca

class _H(dict):
    def get(self, k, d=None): return super().get(k.lower(), d)
class _Req:
    def __init__(self, h=None, c=None):
        self.headers=_H({k.lower(): v for k, v in (h or {}).items()}); self.cookies=c or {}

def main():
    assert ca._normalize_team("https://super-nono.cloudflareaccess.com/")=="super-nono"
    r=_Req({"Cf-Access-Authenticated-User-Email":"Noe@X.fr"})
    assert ca.cf_access_email(r, team="t", aud="a", verify=False)=="noe@x.fr"
    r2=_Req({"Cf-Access-Authenticated-User-Email":"forge@x.fr"})
    assert ca.cf_access_email(r2, team="t", aud="a", verify=True) is None  # pas de jeton
    print("OK port FastAPI")

if __name__ == "__main__":
    main()
