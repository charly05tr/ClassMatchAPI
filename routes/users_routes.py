from models.user import User
from flask import Blueprint, jsonify, request
from flask_login import login_user, login_required, logout_user, current_user
from sqlalchemy import or_, and_
from app import db 
import json

user_bp = Blueprint('user_bp', __name__, url_prefix='/users')

@user_bp.route("/profile/<int:user_id>", methods=["GET", "POST", "PUT", "DELETE"])
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


@user_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    required_fields = ['email', 'name', 'first_name', 'password']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Faltan campos requeridos'}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'El correo ya está registrado'}), 409

    user = User(
        email=data['email'],
        name=data['name'],
        first_name=data['first_name']
    )
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    login_user(user)       
    return jsonify({'message': 'Usuario registrado exitosamente'}), 201


@user_bp.route("/login", methods=["POST"])
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
        'user_id':user.id,
        "message": "Login exitoso",
    }), 200
    
    
@user_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return jsonify({
        "message": "Log out exitoso",
    }), 200
    
    
@user_bp.route("/debug")
def debug():
    return jsonify({
        "authenticated": current_user.is_authenticated,
        "user_id": current_user.get_id() if current_user.is_authenticated else None
    })  
    