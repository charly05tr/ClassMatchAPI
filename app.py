from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, upgrade
from flask import request
from flask_login import LoginManager
from flask_login import  login_required
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import os


app = Flask(__name__)

 
db_url = os.environ.get('DATABASE_URL', 'sqlite:///class_match.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
#test
app.config['SQLALCHEMY_DATABASE_URI'] = db_url

app.secret_key = '50d024439b6e1cf04cbe0c922c083cf2aa3eeca534b9a33b1b51f1af4c35ce9c'
CORS(app, supports_credentials=True, resources={
    r"/*": {
        "origins": [
            "http://0.0.0.0:5173",
            "http://0.0.0.0:5174", 
            'http://192.168.0.6:5173',
            'http://localhost:5173',
            'https://devconnect.network',
            "https://classmatchapi-1.onrender.com", #
        ]
    }
})
socketio = SocketIO(app, cors_allowed_origins=[
    "http://0.0.0.0:5173",
    'https://devconnect.network'
    "http://192.168.0.6:5173",
    "http://127.0.0.1:5173",
    "http://192.168.0.6:5173"
])
if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)


db = SQLAlchemy(app)

from routes.messages_routes import message_bp
from routes.users_routes import user_bp
from routes.projects_routes import project_bp

app.register_blueprint(message_bp)
app.register_blueprint(user_bp)
app.register_blueprint(project_bp)


migrate = Migrate(app, db)

from models.matches import Match
from models.project import Project
from models.user import User
from models.asociation import ProjectUserAssociation
from models.messages import Conversation, Message, ConversationParticipant

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

def activate_migrations():
    upgrade()


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
        })
    return jsonify(result)
    
@app.route("/search", methods=["GET", "POST"])
@login_required 
def search():
    pass
