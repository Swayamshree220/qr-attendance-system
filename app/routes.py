from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_from_directory, current_app, send_file
from flask_login import login_user, current_user, logout_user, login_required
from app import db 
from app.models import User, ClassSession, Attendance
from werkzeug.security import generate_password_hash, check_password_hash 
import qrcode
import uuid 
from datetime import datetime, timedelta
import os
import io
import math
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Message
import csv 
from sqlalchemy import func 

from config import Config
from app.ml_model.proxy_detector import haversine_distance, load_proxy_detector_model, detect_proxy

# NEW TIMEZONE IMPORTS
import pytz
INDIA_TIMEZONE = pytz.timezone('Asia/Kolkata')

bp = Blueprint('routes', __name__)

# --- TIMEZONE CONVERSION UTILITY ---
def convert_utc_to_ist(utc_dt):
    """Converts a naive UTC datetime object to an aware IST datetime object."""
    if utc_dt is None:
        return None
    # 1. Make the naive datetime object aware (as UTC)
    utc_dt_aware = pytz.utc.localize(utc_dt)
    # 2. Convert to the target timezone (IST)
    ist_dt = utc_dt_aware.astimezone(INDIA_TIMEZONE)
    return ist_dt

# --- User Management (omitted for brevity) ---
@bp.route('/')
@bp.route('/home')
def home():
    return render_template('home.html', title='Home')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('routes.home'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash(f'Login successful! Welcome, {user.name}.', 'success')
            return redirect(url_for('routes.home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('routes.home'))

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('routes.home'))
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')

        if not all([student_id, name, email, password, role]):
            flash('All fields are required.', 'danger')
            return render_template('register.html', title='Register')

        if User.query.get(student_id):
            flash('User ID already exists. Please choose a different one.', 'danger')
            return render_template('register.html', title='Register')

        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please use a different email.', 'danger')
            return render_template('register.html', title='Register')

        new_user = User(id=student_id, name=name, email=email, role=role)
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('routes.login'))
    return render_template('register.html', title='Register')

# --- QR Code System ---
@bp.route('/generate_qr_page', methods=['GET', 'POST'])
@login_required
def generate_qr_page():
    if current_user.role != 'teacher':
        flash('Access denied.', 'danger')
        return redirect(url_for('routes.home'))

    qr_image_url = None
    session_id_display = None
    qr_data_string = None
    if request.method == 'POST':
        class_name = request.form.get('class_name')
        expected_latitude = request.form.get('expected_latitude')
        expected_longitude = request.form.get('expected_longitude')

        if not all([class_name, expected_latitude, expected_longitude]):
            flash('All fields are required.', 'danger')
            return render_template('generate_qr.html', title='Generate QR')

        try:
            expected_latitude = float(expected_latitude)
            expected_longitude = float(expected_longitude)
        except ValueError:
            flash('Latitude and Longitude must be valid numbers.', 'danger')
            return render_template('generate_qr.html', title='Generate QR')

        session_id = str(uuid.uuid4())
        qr_data_string = f"CLASS:{class_name}|SESSION:{session_id}|TEACHER:{current_user.id}|LAT:{expected_latitude}|LON:{expected_longitude}|TIME:{datetime.utcnow().isoformat()}"

        new_session = ClassSession(
            id=session_id,
            class_name=class_name,
            teacher_id=current_user.id,
            expected_latitude=expected_latitude,
            expected_longitude=expected_longitude,
            qr_data=qr_data_string
        )
        db.session.add(new_session)
        db.session.commit()
        flash('Class session created successfully!', 'success')

        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
        qr.add_data(qr_data_string)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        qr_filename = f"qr_{session_id}.png"
        qr_filepath = os.path.join(current_app.root_path, 'static', 'qr_codes', qr_filename)
        os.makedirs(os.path.dirname(qr_filepath), exist_ok=True)
        img.save(qr_filepath)
        qr_image_url = url_for('static', filename=f'qr_codes/{qr_filename}')
        flash('QR Code generated!', 'info')
        session_id_display = session_id

    return render_template('generate_qr.html', title='Generate QR', qr_image_url=qr_image_url, qr_data_string=qr_data_string, session_id_display=session_id_display)

@bp.route('/scan_qr_page', methods=['GET'])
@login_required
def scan_qr_page():
    if current_user.role != 'student':
        flash('Access denied.', 'danger')
        return redirect(url_for('routes.home'))
    return render_template('scan_qr.html', title='Scan QR')

@bp.route("/mark-attendance", methods=["POST"])
@login_required
def mark_attendance():
    data = request.get_json()
    qr_data = data.get("qr_data")
    student_id = current_user.id
    
    user_lat = data.get("user_lat")
    user_lon = data.get("user_lon")

    qr_parts = {}
    try:
        for part in qr_data.split('|'):
            key, value = part.split(':', 1)
            qr_parts[key] = value
    except Exception:
        return jsonify({"success": False, "message": "Invalid QR data format."}), 400

    session_id = qr_parts.get('SESSION')
    qr_class_name = qr_parts.get('CLASS')
    qr_teacher_id = qr_parts.get('TEACHER')
    qr_expected_lat = qr_parts.get('LAT')
    qr_expected_lon = qr_parts.get('LON')
    qr_gen_time_str = qr_parts.get('TIME')

    if not all([session_id, qr_class_name, qr_teacher_id, qr_expected_lat, qr_expected_lon, qr_gen_time_str, user_lat, user_lon]):
        return jsonify({"success": False, "message": "Incomplete data. Missing required fields."}), 400

    # --- TIME VALIDATION CHECK ---
    try:
        qr_gen_dt = datetime.fromisoformat(qr_gen_time_str)
        current_dt = datetime.utcnow()
        time_limit = qr_gen_dt + timedelta(minutes=5)

        if current_dt > time_limit:
            return jsonify({"success": False, "message": "Attendance window closed (5-minute limit expired)."}), 403
    except ValueError:
        return jsonify({"success": False, "message": "Error parsing QR code timestamp."}), 400
    # --- END TIME VALIDATION CHECK ---


    class_session = ClassSession.query.get(session_id)
    if not class_session:
        return jsonify({"success": False, "message": "Invalid class session ID."}), 400

    if class_session.teacher_id != qr_teacher_id or class_session.class_name != qr_class_name:
          return jsonify({"success": False, "message": "QR Code data mismatch with session records."}), 400

    student = User.query.get(student_id)
    if not student:
        return jsonify({"success": False, "message": "Student not found in database."}), 404

    try:
        attendance_count = Attendance.query.filter_by(student_id=student_id, session_id=session_id).count()
        if attendance_count >= 2:
            proxy_flag = "Suspicious"
            message = "Attendance already marked multiple times. Flagged as suspicious."
        else:
            scan_timestamp = datetime.utcnow().isoformat()
            
            proxy_flag = detect_proxy(
                user_id=student_id, 
                scan_timestamp=scan_timestamp, 
                qr_gen_timestamp=qr_gen_time_str, 
                user_lat=float(user_lat), 
                user_lon=float(user_lon), 
                qr_lat=float(qr_expected_lat), 
                qr_lon=float(qr_expected_lon)
            )
            message = f"Attendance marked for {student.name}"

        new_attendance = Attendance(
            session_id=session_id,
            student_id=student.id,
            timestamp=datetime.utcnow(),
            is_present=True,
            proxy_detected=proxy_flag
        )
        db.session.add(new_attendance)
        db.session.commit()

        student_info = {
            "name": student.name,
            "roll": student.id,
            "status": "Present",
            "proxy_flag": proxy_flag
        }

        return jsonify({
            "success": True,
            "message": message,
            "student": student_info
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Failed to mark attendance: {e}"}), 500

@bp.route('/static/qr_codes/<filename>')
def served_qr_code(filename):
    return send_from_directory(os.path.join(current_app.root_path, 'static', 'qr_codes'), filename)

# --- Password Reset Routes (omitted for brevity) ---
s = URLSafeTimedSerializer(Config.SECRET_KEY)

@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            token = s.dumps(str(user.id), salt='password-reset-salt')
            reset_url = url_for('routes.reset_token', token=token, _external=True)
            mail = current_app.extensions.get('mail')
            msg = Message('Password Reset Request', sender='your-email@gmail.com', recipients=[user.email])
            msg.body = f'To reset your password, visit the following link: {reset_url}'
            mail.send(msg)
            flash('An email has been sent with instructions to reset your password.', 'info')
            return redirect(url_for('routes.login'))
        else:
            flash('Email not found. Please check your email address.', 'danger')
    return render_template('forgot_password.html', title='Forgot Password')

@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    try:
        user_id = s.loads(token, salt='password-reset-salt', max_age=1800)
    except:
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('routes.forgot_password'))

    user = User.query.get(user_id)
    if user is None:
        flash('Invalid password reset link.', 'danger')
        return redirect(url_for('routes.forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('password')
        if new_password:
            user.set_password(new_password)
            db.session.commit()
            flash('Your password has been reset successfully!', 'success')
            return redirect(url_for('routes.login'))
        else:
            flash('Password cannot be empty.', 'danger')
    return render_template('reset_password.html', title='Reset Password')

# --- TEACHER DASHBOARD LOGIC ---
@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role not in ['teacher', 'admin']:
        flash('Access denied.', 'danger')
        return redirect(url_for('routes.home'))

    # 1. Fetch all sessions created by the current teacher
    teacher_sessions = ClassSession.query.filter_by(teacher_id=current_user.id).order_by(ClassSession.id.desc()).all()
    
    dashboard_data = []
    
    # 2. Loop through sessions and calculate attendance count for each
    for session in teacher_sessions:
        # Calculate unique attendance count for the session
        attendance_count = db.session.query(func.count(func.distinct(Attendance.student_id))).filter(Attendance.session_id == session.id).scalar()
        
        # Parse the QR data string to extract start time
        try:
            # We assume QR data string is safe to parse here: "CLASS:X|SESSION:Y|...|TIME:Z"
            qr_data_dict = dict(item.split(':', 1) for item in session.qr_data.split('|'))
            start_time_str = qr_data_dict.get('TIME', 'N/A')
            class_name = qr_data_dict.get('CLASS', 'N/A') # Ensure CLASS name is extracted

            # Convert UTC to IST before formatting
            start_time_utc = datetime.fromisoformat(start_time_str)
            start_time_ist = convert_utc_to_ist(start_time_utc)
            formatted_time = start_time_ist.strftime('%b %d, %I:%M %p IST')

        except Exception:
            class_name = session.class_name if session.class_name else 'Unknown Class'
            formatted_time = 'Time N/A'

        dashboard_data.append({
            'id': session.id,
            'class_name': class_name,
            'start_time': formatted_time,
            'attendee_count': attendance_count
        })

    return render_template('teacher_dashboard.html', 
                           title='Teacher Dashboard', 
                           sessions=dashboard_data)


# --- STUDENT DASHBOARD LOGIC (Updated to show IST) ---
@bp.route('/student-dashboard', methods=['GET'])
@login_required
def student_dashboard():
    if current_user.role != 'student':
        flash('Access denied.', 'danger')
        return redirect(url_for('routes.home'))

    # FIX 1: Query needs to explicitly include User to handle delete check later
    records = db.session.query(Attendance, ClassSession, User)\
        .join(ClassSession, Attendance.session_id == ClassSession.id)\
        .join(User, Attendance.student_id == User.id)\
        .filter(Attendance.student_id == current_user.id)\
        .order_by(Attendance.timestamp.desc())\
        .all()
    
    # Prepare records for template display (convert time to IST)
    ist_records = []
    for attendance_record, class_session, user in records:
        ist_attendance_time = convert_utc_to_ist(attendance_record.timestamp)
        # FIX 2: Sending (Attendance, ClassSession, User, IST_Time) to template
        ist_records.append((attendance_record, class_session, user, ist_attendance_time))
    
    return render_template('student_dashboard.html', 
                           title='My Attendance Records', 
                           records=ist_records)


@bp.route('/delete-attendance/<record_id>', methods=['POST'])
@login_required
def delete_attendance(record_id):
    # Retrieve the record from the database
    record = Attendance.query.get(record_id)
    
    if not record:
        return jsonify({'success': False, 'message': 'Record not found.'}), 404
        
    # CRITICAL SECURITY CHECK: Ensure the logged-in user owns this record.
    if record.student_id != current_user.id:
        return jsonify({'success': False, 'message': 'Permission denied. You can only delete your own records.'}), 403

    try:
        # Perform the deletion
        db.session.delete(record)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Record deleted successfully.'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Database error during deletion: {str(e)}'}), 500

@bp.route('/reports/<session_id>', methods=['GET'])
@login_required
def view_reports(session_id):
    # Fetch Attendance, User, AND ClassSession data
    records_query = db.session.query(Attendance, User, ClassSession)\
        .join(User, Attendance.student_id == User.id)\
        .join(ClassSession, Attendance.session_id == ClassSession.id)\
        .filter(Attendance.session_id == session_id)
        
    attendance_records = records_query.all()
    
    if not attendance_records:
        flash("No attendance records found for this session.", "info")
        return redirect(url_for('routes.home'))

    # Prepare records for template display (convert time to IST)
    ist_records = []
    for attendance_record, user, class_session in attendance_records:
        ist_attendance_time = convert_utc_to_ist(attendance_record.timestamp)
        ist_records.append((attendance_record, user, class_session, ist_attendance_time))
    
    return render_template('reports.html', title='Attendance Report', records=ist_records, session_id=session_id)

@bp.route('/export-report/<session_id>')
@login_required
def export_report(session_id):
    if current_user.role not in ['teacher', 'admin']:
        flash('Access denied.', 'danger')
        return redirect(url_for('routes.home'))

    # Fetch Attendance and Session records together
    records = db.session.query(Attendance, User, ClassSession)\
        .select_from(Attendance)\
        .join(User, Attendance.student_id == User.id)\
        .join(ClassSession, Attendance.session_id == ClassSession.id)\
        .filter(Attendance.session_id == session_id).all()
    
    if not records:
        flash("No attendance records to export.", "info")
        return redirect(url_for('routes.view_reports', session_id=session_id))

    # Create an in-memory CSV file
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Define all required header columns
    header = [
        'Student ID', 'Name', 'Timestamp (IST)', 'Proxy Status', 
        'time_diff_minutes', 'distance_km', 'scan_day_of_week', 
        'scan_hour_of_day', 'is_first_scan', 'historical_attendance_rate', 
        'last_attendance_streak', 'is_proxy( 0 or 1 )'
    ]
    writer.writerow(header)
    
    # Write data rows
    for attendance, user, session in records:
        
        # --- Feature Recalculation ---
        scan_dt = attendance.timestamp
        qr_data_dict = dict(item.split(':', 1) for item in session.qr_data.split('|'))
        
        try:
            qr_gen_dt = datetime.fromisoformat(qr_data_dict.get('TIME'))
            time_diff_minutes = round((scan_dt - qr_gen_dt).total_seconds() / 60, 2)
        except (ValueError, TypeError):
            time_diff_minutes = 'N/A'
            
        # NOTE: Without user_lat/lon stored in Attendance, distance must be simulated/placeholder
        distance_km = 'N/A' 
        
        # Convert scan time to IST for the report column
        ist_scan_dt = convert_utc_to_ist(scan_dt)

        # --- Time-based Features ---
        scan_day_of_week = scan_dt.weekday() # Monday is 0 and Sunday is 6
        scan_hour_of_day = scan_dt.hour
        
        # --- Placeholder/Business Logic Features ---
        is_proxy_flag_int = 1 if attendance.proxy_detected == 'Suspicious' else 0
        is_first_scan = 1 if db.session.query(Attendance).filter_by(student_id=user.id).count() == 1 else 0
        historical_attendance_rate = 0.85 # Placeholder
        last_attendance_streak = 5 # Placeholder

        row = [
            user.id,
            user.name,
            ist_scan_dt.strftime('%Y-%m-%d %H:%M:%S IST'),
            attendance.proxy_detected,
            time_diff_minutes,
            distance_km,
            scan_day_of_week,
            scan_hour_of_day,
            is_first_scan,
            historical_attendance_rate,
            last_attendance_streak,
            is_proxy_flag_int
        ]
        writer.writerow(row)
        
    output.seek(0)
    
    # Send the CSV file to the user
    file_name = f'attendance_report_{session_id}.csv'
    return send_file(io.BytesIO(output.getvalue().encode()),
                     mimetype='text/csv',
                     as_attachment=True,
                     download_name=file_name)
@bp.route('/delete-session/<session_id>', methods=['POST'])
@login_required
def delete_session(session_id):
    # 1. Retrieve the session record
    session = ClassSession.query.get(session_id)
    
    if not session:
        return jsonify({'success': False, 'message': 'Session not found.'}), 404
        
    # 2. CRITICAL SECURITY CHECK: Ensure the logged-in user owns this record.
    if session.teacher_id != current_user.id and current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Permission denied. You can only delete your own sessions.'}), 403

    try:
        # 3. Delete dependent records first (Attendance)
        Attendance.query.filter_by(session_id=session_id).delete()
        
        # 4. Delete the session
        db.session.delete(session)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Session and all related attendance records deleted.'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Database error during deletion: {str(e)}'}), 500
