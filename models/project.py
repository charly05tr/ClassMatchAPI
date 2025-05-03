from app import db
from sqlalchemy.sql import func

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    tecnologies = db.Column(db.Text, nullable=True)
    preview_url = db.Column(db.Text, nullable=True)
    code_url = db.Column(db.Text, nullable=True)
    project_image = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    user_associations = db.relationship(
        'ProjectUserAssociation',
        back_populates='project', 
        cascade="all, delete-orphan"
    )
    
    def serializer(self):
        return {
            "id": self.id,
            "project_name": self.project_name,
            "description": self.description,
            "tecnologies": self.tecnologies,
            "preview_url": self.preview_url,
            "code_url": self.code_url,
            "project_image": self.project_image,
            "created_at": self.created_at
        }   