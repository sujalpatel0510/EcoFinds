from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import UserMixin, LoginManager
from datetime import datetime

app = Flask(__name__)
# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:8511@localhost/ecofindsdb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize Extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'