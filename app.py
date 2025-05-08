from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, upgrade # Mantener Migrate si planeas usar migraciones localmente
from flask import request
from flask_login import LoginManager
from flask_login import login_required # Asegúrate de que esto solo se use en rutas HTTP
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect # Importar disconnect
from flask_cors import CORS
import os

# --- Inicialización de la Aplicación Flask ---
app = Flask(__name__)

# --- Configuración de la Base de Datos ---
# Obtener la URL de la base de datos de las variables de entorno
db_url = os.environ.get('DATABASE_URL', 'sqlite:///class_match.db')
# Render a veces usa postgres://, SQLAlchemy prefiere postgresql://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Recomendado para desactivar advertencias

# --- Configuración de Clave Secreta (Importante para Flask-Login y SocketIO) ---
app.secret_key = os.environ.get('SECRET_KEY', 'una_clave_secreta_por_defecto_muy_segura') # Usar variable de entorno

# --- Configuración de CORS ---
# Asegúrate de que los orígenes listados son correctos para tu frontend en desarrollo y producción
CORS(app, supports_credentials=True, resources={
    r"/*": {
        "origins": [
            "http://0.0.0.0:5173",
            "http://0.0.0.0:5174",
            'http://192.168.0.6:5173', # Ajusta si tu IP local cambia
            'http://localhost:5173',
            'https://devconnect.network', # Dominio de tu frontend en producción
            "https://classmatchapi-1.onrender.com", # Dominio de tu backend en Render (si es diferente)
            # Añade otros orígenes si es necesario
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"], # Especifica métodos permitidos
        "allow_headers": ["Content-Type", "Authorization"], # Especifica cabeceras permitidas
    }
})

# --- Inicialización de SocketIO ---
# Configura cors_allowed_origins para SocketIO también
socketio = SocketIO(app, cors_allowed_origins=[
    "http://0.0.0.0:5173",
    'https://devconnect.network',
    "http://192.168.0.6:5173",
    "http://127.0.0.1:5173",
    # Asegúrate de que esta lista coincide con los orígenes de CORS de Flask si usas cookies/credenciales
])


# --- Inicialización de SQLAlchemy ---
db = SQLAlchemy(app)

# --- Inicialización de Flask-Migrate ---
# Mantener esto si planeas usar migraciones para cambios de esquema futuros
migrate = Migrate(app, db)

# --- Importación de Blueprints (Rutas) ---
# Importa tus rutas DESPUÉS de inicializar 'app' y 'db'
from routes.messages_routes import message_bp
from routes.users_routes import user_bp
from routes.projects_routes import project_bp

# --- Registro de Blueprints ---
app.register_blueprint(message_bp)
app.register_blueprint(user_bp)
app.register_blueprint(project_bp)

# --- Importación de Modelos ---
# Importa tus modelos DESPUÉS de inicializar 'db'
# Esto es necesario para que SQLAlchemy conozca tus modelos antes de crear las tablas
from models.matches import Match
from models.project import Project
from models.user import User
from models.asociation import ProjectUserAssociation
from models.messages import Conversation, Message, ConversationParticipant

# --- Configuración de Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Nombre del endpoint de login

@login_manager.user_loader
def load_user(user_id):
    # Carga un usuario por su ID para Flask-Login
    return User.query.get(int(user_id))

# --- Función para aplicar migraciones (mantener si planeas usarlas, pero no se llamará automáticamente aquí) ---
# def activate_migrations():
#     with app.app_context(): # Las operaciones de base de datos necesitan el contexto de la aplicación
#         upgrade() # Aplica las migraciones pendientes

# --- Rutas de Ejemplo (Mantener si son necesarias) ---
@app.route("/", methods=["GET"])
@login_required
def index():
    # Asegúrate de que esta ruta solo se llama si el usuario está autenticado
    users = User.query.limit(10).all()
    result = []
    for user in users:
         # Asegúrate de que user.serializer() existe y funciona correctamente
         result.append(user.serializer()) # Usar el serializer del modelo User
    return jsonify(result)

@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
    # Esta ruta parece incompleta o de ejemplo, asegúrate de su propósito
    pass

# --- Punto de Entrada Principal ---
if __name__ == "__main__":
    # --- ¡AQUÍ SE CREAN LAS TABLAS AUTOMÁTICAMENTE! ---
    # Esto crea las tablas definidas en tus modelos si no existen.
    # NO maneja cambios de esquema después de la creación inicial.
    print("Creando tablas de base de datos si no existen...")
    with app.app_context():
        db.create_all()
    print("Tablas verificadas/creadas.")

    # --- Iniciar el servidor Flask-SocketIO ---
    # Asegúrate de ejecutar esto con 'eventlet' o 'gevent' para producción
    # Ej: $ eventlet app.py
    print("Iniciando servidor Flask-SocketIO...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)

