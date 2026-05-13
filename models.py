from extensions import db, login_manager
from flask_login import UserMixin
from datetime import datetime


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    orders = db.relationship('Order', backref='user', lazy=True)
    artist_profile = db.relationship('Artist', backref='account', uselist=False, foreign_keys='Artist.user_id')


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    artworks = db.relationship('Artwork', backref='category', lazy=True)


class Artist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    bio = db.Column(db.Text)
    photo_url = db.Column(db.String(300), default='')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, unique=True)
    artworks = db.relationship('Artwork', backref='artist', lazy=True)


class Artwork(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(300), default='')
    is_available = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    medium = db.Column(db.String(100))
    dimensions = db.Column(db.String(100))
    year = db.Column(db.Integer)
    stock = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    artist_id = db.Column(db.Integer, db.ForeignKey('artist.id'))
    order_items = db.relationship('OrderItem', backref='artwork', lazy=True)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(120), nullable=False)
    customer_email = db.Column(db.String(120), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)        # PayU requires phone
    customer_address = db.Column(db.Text, nullable=False)
    total = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(30), default='Pending')             # Pending → Confirmed → Shipped → Delivered
    # PayU fields
    payu_txnid = db.Column(db.String(100), nullable=True, unique=True)   # our transaction ID
    payu_mihpayid = db.Column(db.String(100), nullable=True)             # PayU's payment ID
    payu_mode = db.Column(db.String(30), nullable=True)                  # CC / DC / UPI / NB
    payu_status = db.Column(db.String(30), nullable=True)                # success / failure / pending
    payment_status = db.Column(db.String(30), default='Unpaid')          # Unpaid / Paid / Failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    items = db.relationship('OrderItem', backref='order', lazy=True)


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    artwork_id = db.Column(db.Integer, db.ForeignKey('artwork.id'))
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, nullable=False)


class HeroSlide(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(300), nullable=False)
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SiteSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String(500), default='')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get(key, default=''):
        row = SiteSettings.query.filter_by(key=key).first()
        return row.value if row else default

    @staticmethod
    def set(key, value):
        row = SiteSettings.query.filter_by(key=key).first()
        if row:
            row.value = value
        else:
            db.session.add(SiteSettings(key=key, value=value))
        db.session.commit()
