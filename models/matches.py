from app import db
from sqlalchemy.sql import func 
from models.user import User

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    matched_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = db.relationship('User', foreign_keys=[user_id], backref='matches')
    matched_user = db.relationship('User', foreign_keys=[matched_user_id], backref='matched_users')

    def serializer(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "matched_user_id": self.matched_user_id,
            "timestamp": self.timestamp
        }