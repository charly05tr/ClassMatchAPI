from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_login import login_user, login_required, logout_user, current_user

app = Flask(__name__)

app.config["TEMPLATES_AUTO_RELOAD"] = True

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///class_match.db'
app.secret_key = '50d024439b6e1cf04cbe0c922c083cf2aa3eeca534b9a33b1b51f1af4c35ce9c'
db = SQLAlchemy(app)

migrate = Migrate(app, db)

from models.user import User
from models.project import Project


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/", methods=["GET"])
@login_required
def index():
    return render_template('index.html', user=current_user)

@app.route("/messages", methods=["GET", "POST"])
def chat():
    pass

@app.route("/profile", methods=["GET", "PUT"])
def profile():
    pass

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
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
    else:
        return render_template('register.html')

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.get_json()

        if not data or not data.get('email') or not data.get('password'):
            return jsonify({"error": "Correo y contraseña son requeridos"}), 400

        user = User.query.filter_by(email=data['email']).first()

        if user is None or not user.verify_password(data['password']):
            return jsonify({"error": "Credenciales inválidas"}), 401
        
        login_user(user)

        return jsonify({
            "message": "Login exitoso",
        }), 200
    else:
        return render_template('login.html')
    
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route("/search", methods=["GET", "POST"])
def search():
    pass