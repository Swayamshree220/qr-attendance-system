# db_init.py
from app import create_app, db
import os
import sys
import logging

# Ensure logging is set up for visibility during Render's build process
logging.basicConfig(level=logging.INFO)

# 1. Create the app context
app = create_app()

# 2. Execute db.create_all() within the app context
with app.app_context():
    try:
        logging.info("Attempting to connect to database and create tables...")
        # Check if the database is configured (DATABASE_URL must be set)
        # This prevents the script from crashing immediately if the environment variable is missing
        if not app.config.get('SQLALCHEMY_DATABASE_URI'):
            logging.error("DATABASE_URL is not set in environment. Cannot initialize DB.")
            sys.exit(1)

        db.create_all()
        logging.info("Database tables created successfully on PostgreSQL.")
    except Exception as e:
        # If this fails, the build will halt, showing the error in Render logs
        logging.error(f"FATAL ERROR: Could not initialize database. Details: {e}")
        sys.exit(1)
