from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from slugify import slugify
from . import context_processors
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize the database
db = SQLAlchemy()

def create_app():
    app = Flask(__name__)

    for processor in context_processors.all_context_processors:
        app.context_processor(processor)
    
    
    # Configure the app (set database URI and other configs)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///database.db")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "dev_key")
    app.config['DEBUG'] = os.getenv("DEBUG", "False").lower() in ("true", "1")

    # Initialize the database with the app
    db.init_app(app)

    # Import models to ensure they are registered with the app
    with app.app_context():
        from . import models
        db.create_all()  # Create the database tables

    # Register the blueprint (routes)
    from .routes import main
    app.register_blueprint(main)
    app.jinja_env.filters['slugify'] = slugify

    return app