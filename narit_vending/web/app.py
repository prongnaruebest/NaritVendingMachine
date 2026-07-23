"""Flask app factory for the web process.

This module creates the Flask application and registers all blueprints.
It does NOT import gpiozero, motion.py, or any hardware module.
All machine state is obtained via ControllerClient over IPC.
"""

from __future__ import annotations

import logging
from pathlib import Path

from flask import Flask, jsonify, render_template, request

_log = logging.getLogger(__name__)


def create_web_app(ctrl_client=None) -> Flask:
    """Create and configure the Flask web application.

    Args:
        ctrl_client: A ControllerClient instance.  If None a new one is created.
    """
    from narit_vending.web.ipc_client import ControllerClient

    if ctrl_client is None:
        ctrl_client = ControllerClient()

    pkg_dir = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        template_folder=str(pkg_dir / "templates"),
        static_folder=str(pkg_dir / "static"),
    )
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    app.extensions["ctrl"] = ctrl_client

    # ── Global error handlers ──────────────────────────────────────────────────

    @app.errorhandler(400)
    def bad_request(exc):
        return jsonify({"ok": False, "error": str(exc)}), 400

    @app.errorhandler(404)
    def not_found(exc):
        return jsonify({"ok": False, "error": "Not found"}), 404

    @app.errorhandler(503)
    def controller_offline(exc):
        return jsonify({"ok": False, "error": "Controller offline"}), 503

    # ── Request/response middleware ────────────────────────────────────────────

    @app.before_request
    def _log_request():
        _log.info("%s %s", request.method, request.path)

    @app.after_request
    def _no_cache(response):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    @app.after_request
    def _cors(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    # ── Register blueprints ────────────────────────────────────────────────────
    from narit_vending.web.routes.commands import make_commands_bp
    from narit_vending.web.routes.config import make_config_bp
    from narit_vending.web.routes.health import make_health_bp
    from narit_vending.web.routes.slots import make_slots_bp
    from narit_vending.web.routes.status import make_status_bp

    app.register_blueprint(make_status_bp(ctrl_client))
    app.register_blueprint(make_commands_bp(ctrl_client))
    app.register_blueprint(make_config_bp(ctrl_client))
    app.register_blueprint(make_slots_bp(ctrl_client))
    app.register_blueprint(make_health_bp(ctrl_client))

    # ── Static HTML entry point ────────────────────────────────────────────────

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/ping")
    def api_ping():
        return jsonify({"ok": True, "message": "pong"}), 200

    return app
