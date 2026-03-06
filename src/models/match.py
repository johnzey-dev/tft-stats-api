from extensions import db


class Match(db.Model):
    __tablename__ = 'matches'

    match_id       = db.Column(db.String,  primary_key=True)
    game_datetime  = db.Column(db.BigInteger, nullable=False)
    game_length    = db.Column(db.Float)
    game_version   = db.Column(db.String)
    tft_set_number = db.Column(db.Integer)
