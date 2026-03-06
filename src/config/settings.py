import os

class Config:
    RIOT_API_KEY = os.getenv('RIOT_API_KEY')
    TIMEOUT = 10  # seconds

    # SQLite via SQLAlchemy — file lives at project root
    _root = os.path.join(os.path.dirname(__file__), '..', '..')
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.abspath(os.path.join(_root, 'cache.db'))}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    PLATFORM_TO_REGION = {
        'na1': 'americas', 'br1': 'americas', 'la1': 'americas', 'la2': 'americas',
        'euw1': 'europe', 'eun1': 'europe', 'tr1': 'europe', 'ru': 'europe',
        'kr': 'asia', 'jp1': 'asia',
        'oc1': 'sea', 'ph2': 'sea', 'sg2': 'sea', 'th2': 'sea', 'tw2': 'sea', 'vn2': 'sea',
    }

    @staticmethod
    def init_app(app):
        pass