from datetime import datetime
from app import db

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
