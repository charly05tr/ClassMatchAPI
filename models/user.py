from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from models.project import Project
import json 
from sqlalchemy.sql import func

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key = True)
    user_name = db.Column(db.String(50), nullable = False)
    email = db.Column(db.String(50), nullable = False)
    name = db.Column(db.String(50), nullable = False)
    first_name = db.Column(db.String(50), nullable = False)
    _password = db.Column("password_hash", db.String(128), nullable=False)
    profile_description = db.Column(db.Text(), nullable=True)
    about_me = db.Column(db.Text(), nullable=True)
    profile_picture = db.Column(db.String(200), nullable=True)
    experience = db.Column(db.Text(), nullable=True)
    education = db.Column(db.Text(), nullable=True)
    location = db.Column(db.String(50), nullable=True)
    skills = db.Column(db.Text(), nullable=True)
    profesion = db.Column(db.String(50), nullable=True)
    social_links = db.Column(db.Text(), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    
    
    sent_messages = db.relationship('Message',foreign_keys='Message.sender_id',back_populates='sender',overlaps="receiver,messages",lazy=True)
    received_messages = db.relationship('Message',foreign_keys='Message.receiver_id',back_populates='receiver',overlaps="sender,messages",lazy=True)
    
    sent_matches = db.relationship('Match',foreign_keys='Match.user_id',back_populates='user',overlaps="matched_user,matches",lazy=True)
    received_matches = db.relationship('Match',foreign_keys='Match.matched_user_id',back_populates='matched_user',overlaps="user,matches",lazy=True)
    
    project_associations = db.relationship('ProjectUserAssociation', back_populates='user', cascade="all, delete-orphan")
    
    def serializer(self):
        social_links_list = []
        if self.social_links:
            try:
                parsed_links = json.loads(self.social_links)
                if isinstance(parsed_links, list):
                    social_links_list = parsed_links
                else:
                     print(f"Warning: social_links data for user {self.id} is not a list: {self.social_links}")
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Error decoding social_links JSON for user {self.id}: {self.social_links} - {e}")
                social_links_list = []
        
        owned_projects_list = []
        collaborated_projects_list = []
        
        for association in self.project_associations:
            if association.project:
                if association.is_owner:
                    owned_projects_list.append(association.project.serializer())
                elif association.is_collaborator:
                    collaborated_projects_list.append(association.project.serializer())
        return {
            "id": self.id,
            "user_name": self.email,
            "profesion": self.profesion,
            "email": self.email,
            "name": self.name,
            "first_name": self.first_name,
            "profile_description": self.profile_description,
            "about_me": self.about_me,
            "profile_picture": self.profile_picture,
            "experience": self.experience,  
            "location": self.location,
            "skills": self.skills, 
            "social_links": social_links_list,
            "created_at": self.created_at,
            "owned_projects": owned_projects_list,
            "collaborated_projects": collaborated_projects_list, 
            "projects_count": len(self.project_associations),
            "match_count": len(self.sent_matches),
            "matched_user_count": len(self.received_matches),
            "education": self.education,
        }
        
    def set_password(self, plane_password):
        self._password = generate_password_hash(plane_password)

    def verify_password(self, plane_password):
        return check_password_hash(self._password, plane_password)
    
