from extensions import db


class User(db.Model):
    __tablename__ = 'users'

    puuid     = db.Column(db.String, primary_key=True)
    game_name = db.Column(db.String, nullable=False)
    tag_line  = db.Column(db.String, nullable=False)
