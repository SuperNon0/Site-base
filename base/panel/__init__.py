"""Site de base — application factory Flask.

Assemble la config, la base SQLite, l'authentification (Cloudflare Zero Trust +
login local), la gestion des comptes et l'intégration des notifications BotPanel.
"""

from __future__ import annotations

import os

from flask import Flask, g, request, session
from jinja2 import ChoiceLoader, FileSystemLoader

from .config import Config


def _load_overlay():
    """Charge la surcouche projet `app` (dossier app/), si présente."""
    try:
        import app as overlay  # noqa: PLC0415
        return overlay
    except Exception:  # pas de surcouche → la base tourne seule (écran de démo)
        return None


def _run_overlay_schema(overlay, db_module) -> None:
    """Exécute app/schema.sql (tables métier de la surcouche), si présent."""
    if overlay is None:
        return
    app_dir = os.path.dirname(os.path.abspath(overlay.__file__))
    schema = os.path.join(app_dir, "schema.sql")
    if os.path.isfile(schema):
        with open(schema, encoding="utf-8") as f:
            db_module.get_db().executescript(f.read())
            db_module.get_db().commit()


def create_app(config_object: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    overlay = _load_overlay()

    # --- Templates : base + surcouche (app/templates prime) ---
    if overlay is not None:
        app_dir = os.path.dirname(os.path.abspath(overlay.__file__))
        tpl = os.path.join(app_dir, "templates")
        if os.path.isdir(tpl):
            app.jinja_loader = ChoiceLoader([FileSystemLoader(tpl), app.jinja_loader])

    from . import db as db_module
    app.teardown_appcontext(db_module.close_db)

    # Schéma base + schéma surcouche (app/schema.sql) + amorce super-admin.
    with app.app_context():
        db_module.init_db()
        _run_overlay_schema(overlay, db_module)

    # --- Blueprints de la base ---
    from .routes.auth_routes import bp as auth_bp
    from .routes.accounts_routes import bp as accounts_bp
    from .routes.system_routes import bp as system_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(system_bp)

    # Écran applicatif : la surcouche fournit le sien ; sinon écran de démo de la base.
    if overlay is not None and hasattr(overlay, "register"):
        overlay.register(app)
    else:
        from .routes.main import bp as main_bp
        app.register_blueprint(main_bp)

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
            # Point d'extension « Réglages » : partial de réglages déclaré par la
            # surcouche (app/__init__.py → flask_app.config["APP_REGLAGES_TEMPLATE"]).
            "app_reglages_template": app.config.get("APP_REGLAGES_TEMPLATE"),
        }

    # --- Toutes les routes /api/* en no-store (spec §8) ---
    @app.after_request
    def no_store_api(resp):
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    return app
