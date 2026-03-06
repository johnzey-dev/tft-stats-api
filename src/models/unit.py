from extensions import db


class Unit(db.Model):
    __tablename__ = 'units'

    unit_id  = db.Column(db.String,  primary_key=True)  # e.g. "TFT16_Shen"
    rarity   = db.Column(db.Integer)
    icon_url = db.Column(db.String)
