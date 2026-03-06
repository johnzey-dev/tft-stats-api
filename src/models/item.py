from extensions import db


class Item(db.Model):
    __tablename__ = 'items'

    item_id  = db.Column(db.String, primary_key=True)  # e.g. "TFT_Item_BlueBuff"
    icon_url = db.Column(db.String)
