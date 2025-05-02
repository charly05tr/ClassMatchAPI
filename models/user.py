from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from models.project import Project
from sqlalchemy.sql import func

project_user = db.Table('project_user',
    db.Column('user_id',db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('project_id',db.Integer, db.ForeignKey('project.id'), primary_key=True),
    db.Column('is_owner', db.Boolean, default=False),
    db.Column('is_collaborator', db.Boolean, default=False),
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key = True)
    user_name = db.Column(db.String(50), nullable = False)
    email = db.Column(db.String(50), nullable = False)
    name = db.Column(db.String(50), nullable = False)
    first_name = db.Column(db.String(50), nullable = False)
    _password = db.Column("password_hash", db.String(128), nullable=False)
    profile_description = db.Column(db.Text(), nullable=False)
    about_me = db.Column(db.Text(), nullable=False)
    profile_picture = db.Column(db.String(200), nullable=False)
    experience = db.Column(db.Text(), nullable=False)
    education = db.Column(db.Text(), nullable=False)
    location = db.Column(db.String(50), nullable=False)
    skills = db.Column(db.Text(), nullable=False)
    profesion = db.Column(db.String(50), nullable=False)
    social_links = db.Column(db.Text(), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    
    matches = db.relationship('Match', foreign_keys='Match.user_id', backref='user', lazy='dynamic')
    matched_users = db.relationship('Match', foreign_keys='Match.matched_user_id', backref='matched_user', lazy='dynamic')
    messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy='dynamic')
    messages_received = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver', lazy='dynamic')
    projects = db.relationship('Project', secondary=project_user, backref='users')
    
    def serializer(self):
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
            "social_links": self.social_links,
            "created_at": self.created_at,
            "owned_projects": [project.serializer() for project in self.projects if project.is_owner],
            "collaborated_projects": [project.serializer() for project in self.projects if project.is_collaborator],
            "projects_count": len(self.projects),
            "match_count": len(self.matches),
            "matched_user_count": len(self.matched_users),
            "education": self.education,
        }
        
    def set_password(self, plane_password):
        self._password = generate_password_hash(plane_password)

    def verify_password(self, plane_password):
        return check_password_hash(self._password, plane_password)
    
