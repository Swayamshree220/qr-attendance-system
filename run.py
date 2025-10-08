# qr_attendance/run.py
from app import create_app, db
from app.models import User, ClassSession, Attendance
from datetime import datetime, timedelta
import uuid
import os # Ensure os is imported here

app = create_app()

with app.app_context():
    # --- Check and create UPLOAD_FOLDER here within the app context ---
    # This ensures app.config is safely accessible
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
        print(f"--- Created UPLOAD_FOLDER: {app.config['UPLOAD_FOLDER']} ---")
    else:
        print(f"--- UPLOAD_FOLDER already exists: {app.config['UPLOAD_FOLDER']} ---")

    db.create_all()
    print("--- Database tables created/ensured. ---")

    if User.query.count() == 0:
        admin = User(id='admin1', name='Admin User', email='admin@example.com', role='admin')
        admin.set_password('admin_password')

        teacher = User(id='teacher1', name='Teacher Jane', email='jane@example.com', role='teacher')
        teacher.set_password('teacher_password')

        student1 = User(id='student1', name='Student Alice', email='alice@example.com', role='student')
        student1.set_password('student_password')

        student2 = User(id='student2', name='Student Bob', email='bob@example.com', role='student')
        student2.set_password('student_password')

        db.session.add_all([admin, teacher, student1, student2])
        db.session.commit()
        print("--- Dummy users created. ---")
    else:
        print("--- Dummy users already exist or database populated. ---")

if __name__ == '__main__':
    app.run(debug=True)