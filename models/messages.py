from sqlalchemy.sql import func
from app import db

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    messages = db.relationship('Message', back_populates='conversation', lazy='dynamic')
    participants = db.relationship('ConversationParticipant', back_populates='conversation',lazy='selectin')
    creator = db.relationship('User', foreign_keys=[creator_id])
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def serializer(self):
        participants_data = []
        participants_data = [
            p.user.serializer() 
            for p in self.participants 
            if p.user 
        ]

        creator_data = self.creator.serializer() if self.creator else None 
            
        return {
            "id": self.id,
            "name":  self.name if self.name else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "message_count": self.messages.count(),
            "participants": participants_data,
            "creator": creator_data,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None
        }

class ConversationParticipant(db.Model):
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    joined_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    conversation = db.relationship('Conversation', back_populates='participants')
    user = db.relationship('User', back_populates='conversation_participations') 

    def serializer(self):
        return {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "joined_at": self.joined_at,
            "user": self.user.serializer() if self.user else None
        }

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id', ondelete="CASCADE"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)

    sender = db.relationship('User', foreign_keys=[sender_id], back_populates='sent_messages')
   
    conversation = db.relationship('Conversation', back_populates='messages')

    def serializer(self):
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "conversation_id": self.conversation_id, 
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "sender": self.sender.serializer() if self.sender else None
        }