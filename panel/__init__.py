"""Site de base — application factory Flask.

Assemble la config, la base SQLite, l'authentification (Cloudflare Zero Trust +
login local), la gestion des comptes et l'intégration des notifications BotPanel.
"""

from __future__ import annotations

from flask import Flask, g, redirect, request, session, url_for

from .config import Config


def create_app(config_object: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    from . import db as db_module
    app.teardown_appcontext(db_module.close_db)

    # Schéma + amorce du super-admin au démarrage.
    with app.app_context():
        db_module.init_db()

    # --- Blueprints ---
    from .routes.auth_routes import bp as auth_bp
    from .routes.accounts_routes import bp as accounts_bp
    from .routes.main import bp as main_bp
    from .routes.system_routes import bp as system_bp
    from .routes.setup_routes import bp as setup_bp
    from .routes.pwa_routes import bp as pwa_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(setup_bp)
    app.register_blueprint(pwa_bp)

    # --- Écran de configuration au premier lancement ---
    @app.before_request
    def _require_setup():
        # Laisse passer l'écran de setup, les statiques et les fichiers PWA.
        if request.endpoint in ("setup.setup", "setup.setup_post", "static",
                                "pwa.manifest", "pwa.sw"):
            return
        if request.path.startswith("/static"):
            return
        from .settings import is_setup_done
        try:
            if is_setup_done():
                return
            # Déjà un admin avec mot de passe (installé via .env) → pas de setup forcé.
            row = db_module.get_db().execute(
                "SELECT 1 FROM comptes WHERE role = 'super_admin' AND mdp_hash IS NOT NULL LIMIT 1"
            ).fetchone()
            if row is not None:
                return
        except Exception:  # base pas prête → ne bloque pas
            return
        return redirect(url_for("setup.setup"))

    # --- Contexte de template partagé (marque + bandeau impersonation) ---
    @app.context_processor
    def inject_globals():
        from .auth import get_compte, is_base_admin
        from .permissions import any_admin_capability, has_capability
        impersonation = None
        if session.get("impersonator_id"):
            cible = get_compte(session.get("compte_id"))
            if cible is not None:
                impersonation = {"email": cible["email"]}
        return {
            "brand": {
                "prefix": app.config["BRAND_PREFIX"],
                "suffix": app.config["BRAND_SUFFIX"],
                "badge": app.config["BRAND_BADGE"],
            },
            "impersonation": impersonation,
            # Helpers de permissions dans les templates : can('site_update')…
            "can": has_capability,
            "any_admin_capability": any_admin_capability,
            "is_base_admin": is_base_admin,
        }

    # --- Toutes les routes /api/* en no-store (spec §8) ---
    @app.after_request
    def no_store_api(resp):
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    return app
