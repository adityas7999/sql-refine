"""SQLRefine Flask application factory."""

import logging

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pymysql import MySQLError
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix

from audit import audit
from config import Config
from connection_manager import ConnectionManager
from errors import ApiError, DatabaseAccessError
from routes.query_routes import api


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    if app.config["TRUST_PROXY_HEADERS"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    CORS(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Connection-Session"],
        expose_headers=[], supports_credentials=False, max_age=600,
    )
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=[app.config["RATELIMIT_DEFAULT"]],
        storage_uri=app.config["RATELIMIT_STORAGE_URI"],
    )
    app.extensions["connection_manager"] = ConnectionManager(app.config)
    app.extensions["limiter"] = limiter
    app.register_blueprint(api)

    app.view_functions["api.test_connection"] = limiter.limit("10 per minute")(app.view_functions["api.test_connection"])
    app.view_functions["api.create_connection_session"] = limiter.limit("10 per minute")(app.view_functions["api.create_connection_session"])
    app.view_functions["api.analyze"] = limiter.limit("20 per minute")(app.view_functions["api.analyze"])

    @app.get("/")
    def root():
        return jsonify({"service": "SQLRefine API", "health": "/api/health", "readiness": "/api/ready"})

    @app.errorhandler(ApiError)
    def api_error(error):
        return jsonify({"error": {"code": error.code, "message": error.message}}), error.status

    @app.errorhandler(MySQLError)
    def mysql_error(error):
        audit("api.database_error", outcome="failure", error_type=type(error).__name__)
        sanitized = DatabaseAccessError()
        return jsonify({"error": {"code": sanitized.code, "message": sanitized.message}}), sanitized.status

    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(_error):
        return jsonify({"error": {"code": "REQUEST_TOO_LARGE", "message": "The request body is too large."}}), 413

    @app.errorhandler(429)
    def rate_limited(_error):
        return jsonify({"error": {"code": "RATE_LIMITED", "message": "Too many requests. Try again shortly."}}), 429

    @app.errorhandler(Exception)
    def unexpected_error(error):
        if isinstance(error, HTTPException):
            return jsonify({"error": {"code": "HTTP_ERROR", "message": error.description}}), error.code
        app.logger.error("Unhandled request failure: %s", type(error).__name__)
        audit("api.unhandled_error", outcome="failure", error_type=type(error).__name__, path=request.path)
        return jsonify({"error": {"code": "INTERNAL_ERROR", "message": "The request could not be completed."}}), 500

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=app.config["DEBUG"])
