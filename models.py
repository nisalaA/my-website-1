from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    cart_items = db.relationship('CartItem', backref='user', lazy=True)
    orders = db.relationship('Order', backref='user', lazy=True)
    shipping_addresses = db.relationship('ShippingAddress', backref='user', lazy=True)
    seller_account = db.relationship('Seller', backref='owner', uselist=False)

    def get_shipping_info(self):
        default_address = ShippingAddress.query.filter_by(user_id=self.id, is_default=True).first()
        if default_address:
            return default_address.to_dict()
        return None

    def is_seller(self):
        return self.seller_account is not None

    def has_approved_seller_account(self):
        return self.seller_account is not None and self.seller_account.status == 'approved'

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_from_user = db.Column(db.Boolean, default=True)
    requires_admin_attention = db.Column(db.Boolean, default=False)
    is_handled = db.Column(db.Boolean, default=False)
    admin_response = db.Column(db.Text)
    
    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'is_from_user': self.is_from_user,
            'requires_admin_attention': self.requires_admin_attention,
            'is_handled': self.is_handled,
            'admin_response': self.admin_response
        }
