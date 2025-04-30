from app import db
from werkzeug.security import generate_password_hash, check_password_hash

project_user = db.Table('project_user',
    db.Column('user_id',db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('project_id',db.Integer, db.ForeignKey('project.id'), primary_key=True)
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    user_name = db.Column(db.String(50), nullable = False)
    email = db.Column(db.String(50), nullable = False)
    name = db.Column(db.String(50), nullable = False)
    first_name = db.Column(db.String(50), nullable = False)
    _password = db.Column("password_hash", db.String(128), nullable=False)
    
    projects = db.relationship('project', secondary=project_user, backref='users')
    
    def serializer(self):
        return {
            "id": self.id,
            "user_name": self.email,
            "email": self.email,
            "name": self.name,
            "first_name": self.first_name
        }
        
    def set_password(self, plane_password):
        self._password = generate_password_hash(plane_password)

    def verify_password(self, plane_password):
        return check_password_hash(self._contrasena, plane_password)
    
