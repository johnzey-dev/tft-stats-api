from extensions import db


class TraitStats(db.Model):
    __tablename__ = 'trait_stats'

    match_id     = db.Column(db.String,  nullable=False, primary_key=True)
    puuid        = db.Column(db.String,  nullable=False, primary_key=True)
    trait_id     = db.Column(db.String,  db.ForeignKey('traits.trait_id'), nullable=False, primary_key=True)
    num_units    = db.Column(db.Integer)
    style        = db.Column(db.Integer)
    tier_current = db.Column(db.Integer)
    tier_total   = db.Column(db.Integer)

    __table_args__ = (
        db.ForeignKeyConstraint(
            ['match_id', 'puuid'],
            ['user_match_stats.match_id', 'user_match_stats.puuid'],
        ),
    )

    user_match = db.relationship('UserMatchStats', back_populates='trait_stats')
    trait      = db.relationship('Trait', lazy='joined')
