# qr_attendance/app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from config import Config
import os

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'routes.login'
login_manager.login_message_category = 'info'
mail = Mail()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    # Move these imports inside the function to fix the circular dependency
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(user_id)

    from app import routes
    app.register_blueprint(routes.bp)

    return app