from app import db
from sqlalchemy.sql import func

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    tecnologies = db.Column(db.Text, nullable=False)
    project_url = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())