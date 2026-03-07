import logging

from flask import Flask
from dotenv import load_dotenv
from config.settings import Config
from extensions import db, migrate
from api.routes.stats import stats_bp

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
)

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
migrate.init_app(app, db)

import models  # noqa: F401 – registers all models with SQLAlchemy / Alembic

app.register_blueprint(stats_bp)

if __name__ == '__main__':
    app.run(debug=True, port=5001, threaded=True)