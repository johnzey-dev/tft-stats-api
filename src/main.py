import logging

from flask import Flask
from dotenv import load_dotenv
from api.routes.stats import stats_bp

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
)

app = Flask(__name__)
app.register_blueprint(stats_bp)

if __name__ == '__main__':
    app.run(debug=True, port=5001, threaded=True)