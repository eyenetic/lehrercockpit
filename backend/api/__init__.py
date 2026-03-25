"""
API Blueprints für das Lehrer-Cockpit Multi-User-System.
"""
from flask import Flask
from .auth_routes import auth_bp
from .admin_routes import admin_bp
from .dashboard_routes import dashboard_bp
from .module_routes import module_bp


def register_blueprints(app: Flask) -> None:
    """Registriert alle API-Blueprints an der Flask-App."""
    app.register_blueprint(auth_bp, url_prefix="/api/v2/auth")
    app.register_blueprint(admin_bp, url_prefix="/api/v2/admin")
    app.register_blueprint(dashboard_bp, url_prefix="/api/v2/dashboard")
    app.register_blueprint(module_bp, url_prefix="/api/v2/modules")
