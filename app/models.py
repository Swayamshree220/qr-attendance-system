# qr_attendance/app/models.py
from app import db
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model, UserMixin):
    id = db.Column(db.String(100), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='student', nullable=False) # 'student', 'teacher', 'admin'
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ClassSession(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    class_name = db.Column(db.String(100), nullable=False)
    teacher_id = db.Column(db.String(100), db.ForeignKey('user.id'), nullable=False)
    expected_latitude = db.Column(db.Float, nullable=False)
    expected_longitude = db.Column(db.Float, nullable=False)
    qr_data = db.Column(db.Text, nullable=False)

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), db.ForeignKey('class_session.id'), nullable=False)
    student_id = db.Column(db.String(100), db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_present = db.Column(db.Boolean, default=True)
    proxy_detected = db.Column(db.String(20), default='Legit') # 'Legit' or 'Suspicious'