from extensions import db


class Trait(db.Model):
    __tablename__ = 'traits'

    trait_id = db.Column(db.String, primary_key=True)  # e.g. "TFT16_Brawler"
    icon_url = db.Column(db.String)
