from extensions import db


class UserMatchStats(db.Model):
    __tablename__ = 'user_match_stats'

    match_id           = db.Column(db.String,  db.ForeignKey('matches.match_id'), primary_key=True)
    puuid              = db.Column(db.String,  db.ForeignKey('users.puuid'),      primary_key=True)
    placement          = db.Column(db.Integer)
    damage_to_players  = db.Column(db.Integer)
    gold_left          = db.Column(db.Integer)
    last_round         = db.Column(db.Integer)
    level              = db.Column(db.Integer)
    players_eliminated = db.Column(db.Integer)
    time_eliminated    = db.Column(db.Float)
    win                = db.Column(db.Boolean)
    augments           = db.Column(db.JSON)    # list of augment name strings

    match       = db.relationship('Match')
    user        = db.relationship('User')
    unit_stats  = db.relationship('UnitStats',  back_populates='user_match', lazy='selectin')
    trait_stats = db.relationship('TraitStats', back_populates='user_match', lazy='selectin')
