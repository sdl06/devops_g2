"""Flask application configuration."""

import os
import secrets
from pathlib import Path

from flask import Flask, jsonify, request, session
from flask_migrate import Migrate
from sqlalchemy.exc import SQLAlchemyError

from .models import db


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URL",
            "sqlite:///" + str(Path(__file__).resolve().parent.parent / "split.sqlite3"),
        ),
        BILL_SERVICE_URL=os.environ.get("BILL_SERVICE_URL", ""),
        STAFF_API_TOKEN=os.environ.get("STAFF_API_TOKEN", ""),
        STAFF_USERNAME=os.environ.get("STAFF_USERNAME", ""),
        STAFF_PASSWORD_HASH=os.environ.get("STAFF_PASSWORD_HASH", ""),
        CORS_ORIGINS=os.environ.get("CORS_ORIGINS", ""),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE=os.environ.get("COOKIE_SAMESITE", "Lax").title(),
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "false").lower() == "true",
    )
    if config:
        app.config.update(config)
    if app.config["SESSION_COOKIE_SAMESITE"] == "None" and not app.config["SESSION_COOKIE_SECURE"]:
        raise ValueError("COOKIE_SAMESITE=None requires COOKIE_SECURE=true.")

    allowed_origins = {origin.strip() for origin in app.config["CORS_ORIGINS"].split(",")}
    allowed_origins.difference_update({"", "*", "null"})
    db.init_app(app)
    Migrate(app, db)
    from .routers import api

    app.register_blueprint(api, url_prefix="/api")

    @app.after_request
    def add_cors_headers(response):
        if request.endpoint == "split.browser_staff_progress":
            return response
        if not allowed_origins or not request.path.startswith("/api/"):
            return response
        response.vary.add("Origin")
        origin = request.headers.get("Origin")
        if origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            if request.method == "OPTIONS" and request.url_rule is not None:
                methods = request.url_rule.methods - {"OPTIONS"}
                response.headers["Access-Control-Allow-Methods"] = ", ".join(sorted(methods))
                response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken"
        return response

    @app.before_request
    def protect_csrf():
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            expected = session.get("csrf_token")
            supplied = request.headers.get("X-CSRFToken", "")
            if not expected or not secrets.compare_digest(expected, supplied):
                return jsonify(error="Missing or invalid CSRF token."), 403

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        db.session.rollback()
        app.logger.exception("Database operation failed")
        return jsonify(error="Database is unavailable. Try again shortly."), 503

    return app
