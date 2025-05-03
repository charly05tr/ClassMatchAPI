from app import db 
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from sqlalchemy.sql import func
import json 

class ProjectUserAssociation(db.Model):
    __tablename__ = 'project_user' 

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), primary_key=True) 

    is_owner = db.Column(db.Boolean, default=False, nullable=False)
    is_collaborator = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship('User', back_populates='project_associations') 
    project = db.relationship('Project', back_populates='user_associations') 

