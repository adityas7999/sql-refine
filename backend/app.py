"""SQLRefine Flask application factory."""

from flask import Flask, jsonify
from flask_cors import CORS

from config import Config
from routes.query_routes import api


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    CORS(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    app.register_blueprint(api)

    @app.get("/")
    def root():
        return jsonify({"service": "SQLRefine API", "health": "/api/health"})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)

