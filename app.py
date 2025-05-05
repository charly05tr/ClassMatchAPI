from flask import Flask, jsonify, redirect, request, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, upgrade
from flask_login import LoginManager
from flask_login import login_user, login_required, logout_user, current_user
from flask_cors import CORS
import json
import os
app = Flask(__name__)
 
db_url = os.environ.get('DATABASE_URL', 'sqlite:///class_match.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url

app.secret_key = '50d024439b6e1cf04cbe0c922c083cf2aa3eeca534b9a33b1b51f1af4c35ce9c'
CORS(app, supports_credentials=True, resources={
    r"/*": {
        "origins": [
            "http://localhost:5173",                 
            "https://classmatchapi-1.onrender.com"   
        ]
    }
})

db = SQLAlchemy(app)
migrate = Migrate(app, db)

from models.messages import Message
from models.matches import Match
from models.project import Project
from models.user import User
from models.asociation import ProjectUserAssociation


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

def activate_migrations():
    upgrade()
  
with app.app_context():  
    db.create_all()  

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/", methods=["GET"])
@login_required 
def index():
    users = User.query.limit(10).all()
    result = []
    for user in users:
        result.append({
            'id': user.id,  
            "name": user.name,
            "profesion": user.profesion,
            "profile_picture": user.profile_picture,
            "match_count": len(user.sent_matches) + len(user.received_matches),
            "projects_count": len(user.project_associations),
            'first_name': user.first_name,
            'user_name': user.user_name,
        })
    return jsonify(result)

@app.route("/messages", methods=["GET", "POST"])
@login_required 
def chat():
    pass

@app.route("/profile/<int:user_id>", methods=["GET", "POST", "PUT", "DELETE"])
@login_required
def profile(user_id):
    user = User.query.get(user_id)
    if request.method == "GET":
        
        return jsonify(user.serializer())

    elif request.method == "POST" and current_user.id == user_id:
        data = request.get_json()
        optional_fields = [
            "profile_description", "about_me", "profile_picture", 
            "education", "location", "skills",
            "profesion",
        ]
        for field in optional_fields:
            if field in data:                
                 setattr(user, field, data[field])
        if "social_links" in data:
             social_links_from_frontend = data.get("social_links")
             if isinstance(social_links_from_frontend, list):
                 user.social_links = json.dumps(social_links_from_frontend)
             elif social_links_from_frontend is None:
                  user.social_links = None
             else:
                 return jsonify({"error": "'social_links' field must be a list or null"}), 400

        if "experience" in data:
            work_experience_from_frontend = data.get("experience")
            if isinstance(work_experience_from_frontend, list):
                user.experience = json.dumps(work_experience_from_frontend)
                print(f"user.work_experience: {user.work_experience}")
            elif work_experience_from_frontend is None:
                user.experience = None
            else:
                return jsonify({"error": "'work_experience' field must be a list or null"}), 400
        try:
            db.session.add(user) 
            db.session.commit()
            return jsonify(user.serializer()), 201 
        except Exception as e:
            db.session.rollback()
            print(f"Error during profile POST commit: {e}")
            return jsonify({"error": "Error al crear el perfil.", "details": str(e)}), 500

    elif request.method == "PUT" and current_user.id == user_id:
        data = request.get_json()
        editable_fields = [
            "user_name", "name", "first_name", "profile_description",
            "about_me", "profile_picture", "education",
            "location", "skills", "profesion",
        ]
        for field in editable_fields:
            if field in data:
                setattr(user, field, data[field])
        if "social_links" in data:
            social_links_from_frontend = data.get("social_links")
            if isinstance(social_links_from_frontend, list):             
                user.social_links = json.dumps(social_links_from_frontend)
            elif social_links_from_frontend is None:
                user.social_links = None
            else:
                return jsonify({"error": "'social_links' field must be a list or null"}), 400

        if "experience" in data:
            work_experience_from_frontend = data.get("experience")       
            if isinstance(work_experience_from_frontend, list):             
                user.experience = json.dumps(work_experience_from_frontend)          
            elif work_experience_from_frontend is None:
                user.experience = None
            else:
                return jsonify({"error": "'work_experience' field must be a list or null"}), 400   
        try:
            db.session.add(user) 
            db.session.commit()
            db.session.refresh(user)
        except Exception as e:
            db.session.rollback()
            print(f"Error during profile PUT commit: {e}")
            return jsonify({"error": "Error al guardar el perfil en la base de datos.", "details": str(e)}), 500
        
        return jsonify(user.serializer()), 200  

    elif request.method == "DELETE" and current_user.id == user_id:      
        fields_to_clear = [
            "profile_description", "about_me", "profile_picture",
            "education", "location", "skills",
            "profesion",             
        ]
        for field in fields_to_clear:             
             if hasattr(user.__class__, field):
                setattr(user, field, None)
        try:
             db.session.add(user)
             db.session.commit()
        except Exception as e:
             db.session.rollback()
             print(f"Error during profile DELETE commit: {e}")
             return jsonify({"error": "Error al eliminar información del perfil.", "details": str(e)}), 500

        return jsonify({"message": "Información eliminada exitosamente"}), 200

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    required_fields = ['user_name', 'email', 'name', 'first_name', 'password']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Faltan campos requeridos'}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'El correo ya está registrado'}), 409

    user = User(
        user_name=data['user_name'],
        email=data['email'],
        name=data['name'],
        first_name=data['first_name']
    )
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()

    login_user(user)
        
    return jsonify({'message': 'Usuario registrado exitosamente'}), 201

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    if not data or not data.get('email') or not data.get('password'):
        return jsonify({"error": "Correo y contraseña son requeridos"}), 400

    user = User.query.filter_by(email=data['email']).first()

    if user is None or not user.verify_password(data['password']):
        return jsonify({"error": "Credenciales inválidas"}), 401
        
    login_user(user)
    print(user.email)
    print( user.is_authenticated)
    return jsonify({
        "message": "Login exitoso",
    }), 200
    
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route("/search", methods=["GET", "POST"])
@login_required 
def search():
    pass

@app.route("/debug")
def debug():
    return jsonify({
        "authenticated": current_user.is_authenticated,
        "user_id": current_user.get_id() if current_user.is_authenticated else None
    })  
    

@app.route("/projects/<int:user_id>", methods=["GET", "PUT"])
@login_required
def user_projects(user_id):

    user = User.query.get(user_id)

    if request.method == "GET":
        projects_list = []
        
        for association in user.project_associations:
            if association.project:
                project_data = association.project.serializer()
                projects_list.append(project_data)

        return jsonify(projects_list), 200

    elif request.method == "PUT" and current_user.id == user_id:
        data = request.get_json()
        if not data or 'projects' not in data or not isinstance(data['projects'], list):
            return jsonify({"error": "Formato de datos incorrecto. Se espera un objeto con una clave 'projects' que contenga una lista."}), 400
        incoming_projects_data = data['projects']

        current_associations_map = {assoc.project_id: assoc for assoc in user.project_associations if assoc.project}
        incoming_project_ids = set()

        for project_data in incoming_projects_data:
            if not isinstance(project_data, dict):
                print(f"Advertencia: Skipping invalid item in incoming projects list: {project_data}")
                continue

            project_id = project_data.get('id')
            if project_id is not None and project_id in current_associations_map:
                association_obj = current_associations_map[project_id]
                project_obj = association_obj.project 

                incoming_project_ids.add(project_id)

                project_update_map = {
                    'project_name': 'project_name',
                    'description': 'description',
                    'tecnologies': 'tecnologies',
                    'preview_url': 'preview_url',
                    'code_url': 'code_url',
                    'project_image': 'project_image',
                }

                not_null_fields = ['project_name', 'description'] 

                is_update_valid = True 

                for incoming_key, backend_attr in project_update_map.items():
                  
                    if incoming_key in project_data:
                         value = project_data.get(incoming_key) 

                         if backend_attr in not_null_fields and value is None:
                              
                              print(f"Error de validación: Received null value for required field '{incoming_key}' (maps to '{backend_attr}') for project ID {project_id}.")
                              is_update_valid = False    
                              break
                         if is_update_valid:
                            setattr(project_obj, backend_attr, value)
                if is_update_valid:
                    db.session.add(project_obj)
                    db.session.add(association_obj) 
                else:  
                    pass 
            else: 
                required_fields_new = ["name", "description", "tecnologies"]
                
                if not all(field in project_data and project_data.get(field) is not None for field in required_fields_new):
                    print(f"Warning: Skipping creation of new project due to missing or null required fields: {project_data}")
                    continue 

                new_project = Project(
                    project_name=project_data.get('name'),
                    description=project_data.get('description'),
                    tecnologies=project_data.get('tecnologies'), 
                    preview_url=project_data.get('url_preview'),
                    code_url=project_data.get('url_code'),
                    project_image=project_data.get('image')
                    
                )
                new_association = ProjectUserAssociation(
                    user=user,
                    project=new_project,
                    is_owner=True,
                    is_collaborator=False
                )
                db.session.add(new_project)
                db.session.add(new_association)

        project_ids_to_delete = [
             project_id for project_id in current_associations_map.keys()
             if project_id not in incoming_project_ids
        ]

        for project_id_to_delete in project_ids_to_delete:
            
             association_to_delete = current_associations_map[project_id_to_delete]

             project_obj_to_delete = association_to_delete.project
             if project_obj_to_delete: 
                 db.session.delete(project_obj_to_delete)
         
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback() 
            print(f"Error during project save commit for user {user.id}: {e}")

            return jsonify({"error": "Error al guardar los proyectos en la base de datos.", "details": str(e)}), 500 

        db.session.refresh(user)
       
        profile_data_with_projects = user.serializer()

        return jsonify(profile_data_with_projects), 200 

