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
        SECRET_KEY=os.environ.get('SECRET_KEY') or secrets.token_hex(32),
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', 'sqlite:///' + str(Path(__file__).resolve().parent.parent / 'split.sqlite3')),
        BILL_SERVICE_URL=os.environ.get('BILL_SERVICE_URL', ''),
        STAFF_API_TOKEN=os.environ.get('STAFF_API_TOKEN', ''),
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE', 'false').lower() == 'true',
    )
    if config:
        app.config.update(config)
    db.init_app(app)
    Migrate(app, db)
    from .routers import api
    app.register_blueprint(api, url_prefix='/api')

    @app.before_request
    def protect_csrf():
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            expected = session.get('csrf_token')
            supplied = request.headers.get('X-CSRFToken', '')
            if not expected or not secrets.compare_digest(expected, supplied):
                return jsonify(error='Missing or invalid CSRF token.'), 403

    @app.get('/health')
    def health():
        return jsonify(status='ok')

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        db.session.rollback()
        app.logger.exception('Database operation failed')
        return jsonify(error='Database is unavailable. Try again shortly.'), 503

    return app
