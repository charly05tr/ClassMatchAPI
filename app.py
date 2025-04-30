from flask import Flask, jsonify, redirect, render_template, request, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

app = Flask(__name__)

app.config["TEMPLATES_AUTO_RELOAD"] = True

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///class_match.db'

db = SQLAlchemy(app)

migrate = Migrate(app, db)

from models.user import User
from models.project import Project

with app.app_context():  
    db.create_all()     

@app.route("/", methods=["GET"])
def index():
    return render_template('index.html')


#comandos para generar migraciones al db:
    #flask db migrate -m "agregue una columna nueva"   
    #flask db upgrade