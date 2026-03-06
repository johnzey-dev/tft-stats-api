from extensions import db


class UnitStats(db.Model):
    __tablename__ = 'unit_stats'

    id        = db.Column(db.Integer, primary_key=True, autoincrement=True)
    match_id  = db.Column(db.String,  nullable=False)
    puuid     = db.Column(db.String,  nullable=False)
    unit_id   = db.Column(db.String,  db.ForeignKey('units.unit_id'), nullable=False)
    unit_tier = db.Column(db.Integer)

    __table_args__ = (
        db.ForeignKeyConstraint(
            ['match_id', 'puuid'],
            ['user_match_stats.match_id', 'user_match_stats.puuid'],
        ),
    )

    user_match      = db.relationship('UserMatchStats', back_populates='unit_stats')
    unit            = db.relationship('Unit', lazy='joined')
    unit_stat_items = db.relationship(
        'UnitStatsItem', back_populates='unit_stats',
        lazy='selectin', cascade='all, delete-orphan',
    )


class UnitStatsItem(db.Model):
    __tablename__ = 'unit_stats_items'

    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    unit_stats_id = db.Column(db.Integer, db.ForeignKey('unit_stats.id'),   nullable=False)
    item_id       = db.Column(db.String,  db.ForeignKey('items.item_id'),   nullable=False)

    unit_stats = db.relationship('UnitStats', back_populates='unit_stat_items')
    item       = db.relationship('Item', lazy='joined')
