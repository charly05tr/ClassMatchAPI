from flask import Flask, jsonify, redirect, request, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_login import login_user, login_required, logout_user, current_user
from flask_cors import CORS

app = Flask(__name__)
 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///class_match.db'
app.secret_key = '50d024439b6e1cf04cbe0c922c083cf2aa3eeca534b9a33b1b51f1af4c35ce9c'
CORS(app, supports_credentials=True, resources={r"/*": {"origins": "http://localhost:5173"}})
db = SQLAlchemy(app)

migrate = Migrate(app, db)

from models.user import User
from models.project import Project
from models.messages import Message 
from models.matches import Match


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
  
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
            "name": user.name,
            "profesion": user.profesion,
            "profile_picture": user.profile_picture,
            "match_count": len(user.matches),
            "projects_count": len(user.projects),
            "skills": user.skills
        })
    return jsonify(result)

@app.route("/messages", methods=["GET", "POST"])
@login_required 
def chat():
    pass

@app.route("/profile", methods=["GET", "POST", "PUT", "DELETE"])
@login_required
def profile():
    if request.method == "GET":
        # Retorna el serializer del usuario actual
        return jsonify(current_user.serializer())

    elif request.method == "POST":
        # Maneja las entradas de los campos adicionales
        data = request.get_json()
        optional_fields = [
            "profile_description", "about_me", "profile_picture",
            "experience", "education", "location", "skills",
            "profesion", "social_links"
        ]
        for field in optional_fields:
            if field in data:
                setattr(current_user, field, data[field])
        db.session.commit()
        return jsonify({"message": "Información adicional actualizada exitosamente"}), 200

    elif request.method == "PUT":
        # Permite editar todos los campos excepto `id` y `email`
        data = request.get_json()
        editable_fields = [
            "user_name", "name", "first_name", "profile_description",
            "about_me", "profile_picture", "experience", "education",
            "location", "skills", "profesion", "social_links"
        ]
        for field in editable_fields:
            if field in data:
                setattr(current_user, field, data[field])
        db.session.commit()
        return jsonify({"message": "Perfil actualizado exitosamente"}), 200

    elif request.method == "DELETE":
        # Elimina los campos que se pueden manejar en POST
        fields_to_clear = [
            "profile_description", "about_me", "profile_picture",
            "experience", "education", "location", "skills",
            "profesion", "social_links"
        ]
        for field in fields_to_clear:
            setattr(current_user, field, None)
        db.session.commit()
        return jsonify({"message": "Información eliminada exitosamente"}), 200

@app.route("/register", methods=["POST"])
@login_required 
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
@login_required 
def login():
    data = request.get_json()

    if not data or not data.get('email') or not data.get('password'):
        return jsonify({"error": "Correo y contraseña son requeridos"}), 400

    user = User.query.filter_by(email=data['email']).first()

    if user is None or not user.verify_password(data['password']):
        return jsonify({"error": "Credenciales inválidas"}), 401
        
    login_user(user)
    print(user.email)
    print( current_user.is_authenticated)
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