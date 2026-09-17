"""Socle-lite — fabrique Flask minimale (auth Cloudflare + secours local, sans compte)."""
from __future__ import annotations

from flask import Flask, request, session

from .config import Config


def create_app(config_object: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    from .auth import bp as auth_bp
    from .main import bp as main_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    @app.context_processor
    def inject_globals():
        return {
            "brand": {
                "prefix": app.config["BRAND_PREFIX"],
                "suffix": app.config["BRAND_SUFFIX"],
                "badge": app.config["BRAND_BADGE"],
            },
            "current_email": session.get("email"),
        }

    @app.after_request
    def no_store_api(resp):
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    return app
