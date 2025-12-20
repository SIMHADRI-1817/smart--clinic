from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, timedelta
import sqlite3
import csv
import random
from io import StringIO

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from authlib.integrations.flask_client import OAuth
import os
import pytz

def get_ist_time():
    return datetime.now(pytz.timezone('Asia/Kolkata'))

# Email Configuration (Placeholders - User to update)
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USERNAME = 'cureconnect25@gmail.com'  
MAIL_PASSWORD = 'hron jiup mlht uqwx'     

def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp_email(to_email, otp):
    try:
        msg = MIMEMultipart()
        msg['From'] = MAIL_USERNAME
        msg['To'] = to_email
        msg['Subject'] = "CureConnect - Verify your email"
        
        body = f"Your verification code is: {otp}"
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT)
        server.starttls()
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(MAIL_USERNAME, to_email, text)
        server.quit()
        return True, None
    except Exception as e:
        print(f"Email Error: {e}")
        return False, str(e)



app = Flask(__name__)
app.secret_key = "dev_secret_for_flash"  # use a strong key for production
DB = 'clinic.db'

# Google OAuth Configuration
app.config['GOOGLE_CLIENT_ID'] = '162547054154-j26fr41mr6lkomqhhmna2k3hpdu3kok0.apps.googleusercontent.com'
app.config['GOOGLE_CLIENT_SECRET'] = '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'
app.config['GOOGLE_DISCOVERY_URL'] = "https://accounts.google.com/.well-known/openid-configuration"

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    server_metadata_url=app.config['GOOGLE_DISCOVERY_URL'],
    client_kwargs={
        'scope': 'openid email profile'
    }
)
 
# -------------------------
# Database connection helper
# -------------------------
def get_db_connection():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn
 
# -------------------------
# Authentication helpers
# -------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function
 
def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            role = session.get('role')
            if role not in allowed_roles:
                flash("You do not have permission to access this page.", "error")
                return redirect(url_for('home'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator
 
def get_current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
    conn.close()
    return user
 
# -------------------------
# Auto-Update Status Helper
# -------------------------
def update_appointment_statuses():
    """
    Checks for appointments that are 1 hour past their scheduled time
    and marks them as 'no_show' if they are still pending or confirmed.
    """
    try:
        conn = get_db_connection()
        # Get appointments that might need updating
        # Excluded 'checked_in' - if they are here, they aren't a no-show!
        appointments = conn.execute(
            "SELECT id, date, time FROM appointments WHERE status IN ('pending', 'confirmed')"
        ).fetchall()
        
        current_time = get_ist_time()
        # Convert naive datetime to aware for comparison
        # current_time is aware (IST). appt_dt will be naive.
        # We need to make appt_dt aware (assuming it was booked in IST).
        
        for appt in appointments:
            try:
                # Handle multiple date formats
                date_str = appt['date']
                try:
                    # Try YYYY-MM-DD first
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    try:
                        # Try DD-MM-YYYY
                        date_obj = datetime.strptime(date_str, '%d-%m-%Y').date()
                    except ValueError:
                        # Skip if date is unparseable
                        print(f"Skipping unparseable date: {date_str}")
                        continue

                # Combine with time
                time_str = appt['time']
                appt_dt_naive = datetime.combine(date_obj, datetime.strptime(time_str, '%H:%M').time())
                # Localize to IST
                appt_dt = pytz.timezone('Asia/Kolkata').localize(appt_dt_naive)
                
                # Check if 1 hour has passed
                if current_time > appt_dt + timedelta(minutes=60):
                    conn.execute(
                        "UPDATE appointments SET status = 'no_show' WHERE id = ?",
                        (appt['id'],)
                    )
            except ValueError:
                # Handle cases where time format might be incorrect
                continue
                
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error updating statuses: {e}")

@app.before_request
def before_request():
    # Run this check on every request (or could limit to specific routes)
    update_appointment_statuses()

@app.route('/debug/fix_statuses')
def debug_fix_statuses():
    log = []
    try:
        conn = get_db_connection()
        appointments = conn.execute(
            "SELECT id, date, time, status, patient_name FROM appointments WHERE status IN ('pending', 'confirmed')"
        ).fetchall()
        
        current_time = get_ist_time()
        log.append(f"Current Time (IST): {current_time}")
        
        updated_count = 0
        
        for appt in appointments:
            try:
                date_str = appt['date']
                date_obj = None
                for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%Y'):
                    try:
                        date_obj = datetime.strptime(date_str, fmt).date()
                        break
                    except ValueError:
                        continue
                
                if not date_obj:
                    log.append(f"ID {appt['id']}: Unparseable date '{date_str}'")
                    continue

                time_str = appt['time']
                appt_dt_naive = datetime.combine(date_obj, datetime.strptime(time_str, '%H:%M').time())
                appt_dt = pytz.timezone('Asia/Kolkata').localize(appt_dt_naive)
                
                # Check if 1 hour has passed
                threshold = appt_dt + timedelta(minutes=60)
                
                if current_time > threshold:
                    conn.execute("UPDATE appointments SET status = 'no_show' WHERE id = ?", (appt['id'],))
                    log.append(f"ID {appt['id']} ({date_str} {time_str}): UPDATED to no_show (Threshold: {threshold})")
                    updated_count += 1
                else:
                    # log.append(f"ID {appt['id']}: Skipped (Threshold: {threshold})")
                    pass
            except Exception as e:
                log.append(f"ID {appt['id']}: Error {e}")
                continue
                
        conn.commit()
        conn.close()
        log.append(f"Total updated: {updated_count}")
    except Exception as e:
        log.append(f"Critical Error: {e}")
        
    return "<br>".join(log)

# -------------------------
# Authentication routes
# -------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        role = request.form.get('role', 'patient').strip()
        if role not in ('patient', 'reception', 'admin', 'doctor'):
             flash("Invalid role selected.", "error")
             return redirect(url_for('login', tab='register'))

        username = request.form.get('username', '').strip()
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '').strip()
        
        if not (username and password and full_name and email):
            flash("All fields are required.", "error")
            return redirect(url_for('login', tab='register'))

        conn = get_db_connection()
        # Check if username exists
        user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if user:
            flash("Username already exists!", "error")
            conn.close()
            return redirect(url_for('login', tab='register'))
            
        # Check if email exists
        user_email = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if user_email:
            flash("Email already registered!", "error")
            conn.close()
            return redirect(url_for('login', tab='register'))
        conn.close()

        # --- OTP FLOW START ---
        hashed = generate_password_hash(password)
        session['temp_user'] = {
            'username': username,
            'full_name': full_name,
            'email': email,
            'phone': phone,
            'password': hashed,
            'role': role
        }
        
        otp = generate_otp()
        session['otp'] = otp
        
        success, error_msg = send_otp_email(email, otp)
        if success:
            flash(f"OTP sent to {email}. Please verify.", "info")
            return redirect(url_for('verify_otp'))
        else:
            flash(f"Error sending OTP: {error_msg}", "error")
            return redirect(url_for('login', tab='register'))

        # --- OTP FLOW END ---
            
    return redirect(url_for('login', tab='register'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if user:
            otp = generate_otp()
            session['reset_email'] = email
            session['reset_otp'] = otp
            session['otp_verified'] = False
            
            if send_otp_email(email, otp):
                flash(f"Reset code sent to {email}.", "info")
                return redirect(url_for('reset_password_otp'))
            else:
                flash("Error sending email. Please try again.", "error")
        else:
            # Don't reveal if email exists or not for security, or do? 
            # For this project, let's be helpful.
            flash("Email not found.", "error")
            
    return render_template('forgot_password.html')

@app.route('/reset-password-otp', methods=['GET', 'POST'])
def reset_password_otp():
    if 'reset_email' not in session or 'reset_otp' not in session:
        flash("Session expired. Please start over.", "error")
        return redirect(url_for('forgot_password'))
        
    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        generated_otp = session.get('reset_otp')
        
        if entered_otp == generated_otp:
            session['otp_verified'] = True
            return redirect(url_for('reset_password_new'))
        else:
            flash("Invalid code. Please try again.", "error")
            
    return render_template('reset_password_otp.html')

@app.route('/reset-password-new', methods=['GET', 'POST'])
def reset_password_new():
    if not session.get('otp_verified'):
        flash("Please verify your code first.", "error")
        return redirect(url_for('forgot_password'))
        
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for('reset_password_new'))
            
        email = session.get('reset_email')
        hashed = generate_password_hash(password)
        
        conn = get_db_connection()
        conn.execute('UPDATE users SET password = ? WHERE email = ?', (hashed, email))
        conn.commit()
        conn.close()
        
        # Clear session
        session.pop('reset_email', None)
        session.pop('reset_otp', None)
        session.pop('otp_verified', None)
        
        flash("Password reset successful! Please login.", "success")
        return redirect(url_for('login'))
        
    return render_template('reset_password_new.html')

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if 'temp_user' not in session or 'otp' not in session:
        flash("Session expired. Please register again.", "error")
        return redirect(url_for('login', tab='register'))
        
    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        generated_otp = session.get('otp')
        
        if entered_otp == generated_otp:
            # OTP Verified! Create User
            user_data = session.get('temp_user')
            
            try:
                conn = get_db_connection()
                conn.execute(
                    'INSERT INTO users (username, full_name, email, phone, password, role) VALUES (?,?,?,?,?,?)',
                    (user_data['username'], user_data['full_name'], user_data['email'], user_data['phone'], user_data['password'], user_data['role'])
                )
                conn.commit()
                conn.close()
                
                # Clear session temp data
                session.pop('temp_user', None)
                session.pop('otp', None)
                
                flash("Account created successfully! Please log in.", "success")
                return redirect(url_for('login'))
                
            except Exception as e:
                flash(f"Error creating account: {e}", "error")
                return redirect(url_for('login', tab='register'))
        else:
            flash("Invalid OTP. Please try again.", "error")
            
    return render_template('verify_otp.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'login':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
 
            conn = get_db_connection()
            user = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
            conn.close()
 
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                session['full_name'] = user['full_name']
                # Store clinic_id for clinic_admin users
                if user['role'] == 'clinic_admin':
                    session['clinic_id'] = user['clinic_id']
                flash("Logged in successfully.", "success")
 
                if user['role'] == 'admin':
                    return redirect(url_for('admin'))
                elif user['role'] == 'clinic_admin':
                    return redirect(url_for('clinic_admin_dashboard'))
                elif user['role'] == 'reception':
                    return redirect(url_for('reception'))
                elif user['role'] == 'doctor':
                    return redirect(url_for('doctor_dashboard'))
                else:
                    return redirect(url_for('patient_dashboard'))
            else:
                flash("Invalid username or password.", "error")
                return redirect(url_for('login'))
        
        elif action == 'signup':
            username = request.form.get('username', '').strip()
            full_name = request.form.get('full_name', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '').strip()
            role = 'patient'
 
            if not (username and password and full_name and email):
                flash("All fields are required for sign up.", "error")
                return redirect(url_for('login'))
 
            hashed = generate_password_hash(password)
            conn = get_db_connection()
            try:
                conn.execute(
                    'INSERT INTO users (username, full_name, email, password, role) VALUES (?,?,?,?,?)',
                    (username, full_name, email, hashed, role)
                )
                conn.commit()
                flash("Account created successfully! Please log in.", "success")
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash("Username or email already exists.", "error")
                return redirect(url_for('login', tab='register'))
            finally:
                conn.close()

        else:
            flash("Invalid action.", "error")
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for('home'))

# -------------------------
# Mock Authentication Routes
# -------------------------
@app.route('/auth/google')
def google_auth():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/google/callback')
def google_callback():
    token = google.authorize_access_token()
    user_info = google.userinfo()
    
    if not user_info:
        flash("Failed to log in with Google.", "error")
        return redirect(url_for('login'))
        
    email = user_info['email']
    name = user_info.get('name', 'Google User')
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
    
    if not user:
        # Create user if not exists
        # Note: We set a random password or handle passwordless login. 
        # For now, we'll generate a random hash so they can't login with password unless they reset it.
        hashed = generate_password_hash(generate_otp() + "google_secret") 
        conn.execute(
            'INSERT INTO users (username, full_name, email, phone, password, role) VALUES (?,?,?,?,?,?)',
            (email, name, email, "0000000000", hashed, 'patient')
        )
        conn.commit()
        user = conn.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
    
    conn.close()
    
    # Log in
    session['user_id'] = user['id']
    session['role'] = user['role']
    session['username'] = user['username']
    session['full_name'] = user['full_name']
    
    flash(f"Successfully logged in as {user['full_name']}", "success")
    
    if user['role'] == 'admin':
        return redirect(url_for('admin'))
    elif user['role'] == 'reception':
        return redirect(url_for('reception'))
    elif user['role'] == 'doctor':
        return redirect(url_for('doctor_dashboard'))
    else:
        return redirect(url_for('patient_dashboard'))

@app.route('/auth/send-otp', methods=['POST'])
def send_otp():
    """
    Simulates sending an OTP to a mobile number.
    In a real app, this would use Twilio or similar.
    Here, we print the OTP to the console.
    """
    data = request.get_json()
    phone = data.get('phone')
    
    if not phone:
        return jsonify({'success': False, 'message': 'Phone number required'})
    
    # Generate 6-digit OTP
    otp = str(random.randint(100000, 999999))
    
    # Store in session
    session['mock_otp'] = otp
    session['mock_phone'] = phone
    
    # Print to console (Mock behavior)
    print(f"\n{'='*40}")
    print(f"📱 MOCK SMS TO {phone}")
    print(f"🔑 OTP CODE: {otp}")
    print(f"{'='*40}\n")
    
    return jsonify({'success': True, 'message': 'OTP sent'})

@app.route('/auth/verify-otp', methods=['POST'])
def mock_verify_otp():
    """
    Verifies the OTP entered by the user.
    """
    data = request.get_json()
    user_otp = data.get('otp')
    
    stored_otp = session.get('mock_otp')
    
    if user_otp and stored_otp and user_otp == stored_otp:
        return jsonify({'success': True, 'message': 'Verified'})
    else:
        return jsonify({'success': False, 'message': 'Invalid OTP'})
 
# -------------------------
# Home route
# -------------------------
@app.route('/')
def home():
    user = get_current_user()
    return render_template('index.html', user=user)

# -------------------------
# Contact Routes
# -------------------------
@app.route('/contact')
def contact():
    user = get_current_user()
    return render_template('contact.html', user=user)

@app.route('/send_message', methods=['POST'])
def send_message():
    name = request.form.get('name')
    email = request.form.get('email')
    message = request.form.get('message')

    print(f"📩 Message from {name} ({email}): {message}")
    flash("Your message has been sent successfully!", "success")
    return redirect(url_for('contact'))

# -------------------------
# About Route
# -------------------------
@app.route('/about')
def about():
    user = get_current_user()
    return render_template('about.html', user=user)

@app.route('/doctors')
def doctors():
    user = get_current_user()
    conn = get_db_connection()
    
    # Fetch doctors with their clinic info
    # Note: If a doctor is in multiple clinics, they will appear multiple times. 
    # For a simple list, this can be acceptable or we might want to group_concat clinic names.
    # Let's simple join for now.
    doctors = conn.execute('''
        SELECT u.full_name, u.specialization, c.name as clinic_name
        FROM users u
        JOIN clinic_staff_association csa ON u.id = csa.user_id
        JOIN clinics c ON csa.clinic_id = c.id
        WHERE u.role = 'doctor' AND csa.is_active = 1
        ORDER BY u.full_name
    ''').fetchall()
    
    conn.close()
    return render_template('doctors.html', user=user, doctors=doctors)

# -------------------------
# Booking route
# -------------------------
@app.route('/booking', methods=['GET', 'POST'])
@login_required
def booking():
    if request.method == 'POST':
        conn = get_db_connection()
        patient = session.get('full_name') or "Unknown"
        patient_id = session.get('user_id')
        doctor_id = request.form.get('doctor_id', '').strip()
        clinic_id = request.form.get('clinic_id', '').strip()
        date = request.form.get('date', '').strip()
        time = request.form.get('time', '').strip()
        reason = request.form.get('reason', '').strip()
        
        # Get doctor and clinic names
        doctor = conn.execute('SELECT full_name FROM users WHERE id=?', (doctor_id,)).fetchone()
        clinic = conn.execute('SELECT name FROM clinics WHERE id=?', (clinic_id,)).fetchone()
        
        if not (doctor and clinic):
            flash("Invalid doctor or clinic selection.", "error")
            conn.close()
            return redirect(url_for('booking'))
        
        doctor_name = doctor['full_name']
        clinic_name = clinic['name']
        
        # Check if slot is already booked
        booked = conn.execute(
            "SELECT id FROM appointments WHERE doctor_id=? AND clinic_id=? AND date=? AND time=? AND status IN ('pending', 'checked_in')",
            (doctor_id, clinic_id, date, time)
        ).fetchone()
        
        if booked:
            flash("This time slot is already booked. Please choose another time.", "error")
            conn.close()
            return redirect(url_for('booking'))
 
        if not (patient and doctor_id and clinic_id and date and time):
            flash("All fields are required.", "error")
            conn.close()
            return redirect(url_for('booking'))

        # Check if booking is in the past
        try:
             # Parse date flexibly
             booking_date = None
             for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%Y'):
                 try:
                     booking_date = datetime.strptime(date, fmt).date()
                     break
                 except ValueError:
                     continue
             
             if not booking_date:
                 raise ValueError("Invalid date format")

             booking_time = datetime.strptime(time, '%H:%M').time()
             booking_dt_naive = datetime.combine(booking_date, booking_time)
             booking_dt = pytz.timezone('Asia/Kolkata').localize(booking_dt_naive)
             
             if booking_dt < get_ist_time():
                 flash("Cannot book appointments in the past. Please choose a future time.", "error")
                 conn.close()
                 return redirect(url_for('booking'))
        except ValueError:
             flash("Invalid date or time format.", "error")
             conn.close()
             return redirect(url_for('booking'))
 
        conn.execute(
            "INSERT INTO appointments (patient_name, doctor_name, doctor_id, clinic_name, clinic_id, date, time, reason, status) VALUES (?,?,?,?,?,?,?,?,?)",
            (patient, doctor_name, doctor_id, clinic_name, clinic_id, date, time, reason, 'pending')
        )
        conn.commit()
        conn.close()
 
        flash("Appointment booked successfully!", "success")
        return redirect(url_for('patient_dashboard'))
 
    return render_template('booking.html')

# -------------------------
# API Endpoints for Booking
# -------------------------
@app.route('/api/get_clinics', methods=['GET'])
@login_required
def get_clinics():
    conn = get_db_connection()
    clinics = conn.execute('SELECT id, name, address FROM clinics ORDER BY name').fetchall()
    conn.close()
    return jsonify([{'id': c['id'], 'name': c['name'], 'address': c['address']} for c in clinics])

@app.route('/api/get_doctors_by_clinic', methods=['GET'])
@login_required
def get_doctors_by_clinic():
    clinic_id = request.args.get('clinic_id')
    if not clinic_id:
        return jsonify({'error': 'Clinic ID is required'}), 400
    
    conn = get_db_connection()
    doctors = conn.execute('''
        SELECT u.id, u.full_name, u.specialization 
        FROM users u
        JOIN doctor_clinics dc ON u.id = dc.doctor_id
        WHERE dc.clinic_id = ? AND u.role = 'doctor'
        ORDER BY u.full_name
    ''', (clinic_id,)).fetchall()
    conn.close()
    
    return jsonify([{
        'id': d['id'], 
        'name': d['full_name'], 
        'specialization': d['specialization']
    } for d in doctors])

@app.route('/api/get_available_slots', methods=['GET'])
@login_required
def get_available_slots():
    doctor_id = request.args.get('doctor_id')
    clinic_id = request.args.get('clinic_id')
    date = request.args.get('date')
    
    if not (doctor_id and clinic_id and date):
        return jsonify({'error': 'Doctor ID, Clinic ID, and Date are required'}), 400
    
    conn = get_db_connection()
    booked_slots = conn.execute(
        "SELECT time FROM appointments WHERE doctor_id=? AND clinic_id=? AND date=? AND status IN ('pending', 'checked_in') ORDER BY time",
        (doctor_id, clinic_id, date)
    ).fetchall()
    
    occupied_times = [slot['time'] for slot in booked_slots]
    
    # helper to generate 30 min slots
    def generate_slots(start_str, end_str):
        slots = []
        try:
            start = datetime.strptime(start_str, '%H:%M')
            end = datetime.strptime(end_str, '%H:%M')
            curr = start
            while curr < end:
                slots.append(curr.strftime('%H:%M'))
                curr += timedelta(minutes=30)
        except Exception as e:
            print(f"Slot gen error: {e}")
        return slots

    # Get day of week
    try:
        dt = datetime.strptime(date, '%Y-%m-%d')
        day_name = dt.strftime('%A') # e.g. "Monday"
    except ValueError:
        conn.close()
        return jsonify({'error': 'Invalid date format'}), 400

    # Check for custom shift
    shift = conn.execute(
        "SELECT start_time, end_time FROM staff_shifts WHERE user_id=? AND clinic_id=? AND day_of_week=? AND is_active=1",
        (doctor_id, clinic_id, day_name)
    ).fetchone()
    
    conn.close()
    
    if shift:
        # Use custom shift
        all_possible_slots = generate_slots(shift['start_time'], shift['end_time'])
    else:
        # Fallback to defaults
        standard_times = [
            '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
            '14:00', '14:30', '15:00', '15:30', '16:00', '16:30'
        ]
        all_possible_slots = standard_times
    
    available_times = [time for time in all_possible_slots if time not in occupied_times]
    
    # Filter past times if date is today
    try:
        # Debugging: Write to a file to verify what we receive
        with open('debug_log.txt', 'a') as f:
             f.write(f"\n[{datetime.now()}] Request Date: '{date}'")

        requested_date = None
        for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%Y'):
            try:
                requested_date = datetime.strptime(date, fmt).date()
                break
            except ValueError:
                continue
        
        if not requested_date:
            with open('debug_log.txt', 'a') as f:
                f.write(" -> Failed to parse date!")
            raise ValueError("Invalid date format")

        now = get_ist_time()
        with open('debug_log.txt', 'a') as f:
             f.write(f" -> Parsed: {requested_date}, ServerToday: {now.date()}")

        if requested_date == now.date():
            current_time = now.time()
            available_times = [t for t in available_times if datetime.strptime(t, '%H:%M').time() > current_time]
    except Exception as e:
        with open('debug_log.txt', 'a') as f:
             f.write(f" -> ERROR: {e}")
        pass
    
    return jsonify({'available_times': available_times})

# -------------------------
# Doctor Availability API
# -------------------------
@app.route('/api/doctor_availability', methods=['GET'])
@login_required
def doctor_availability():
    doctor_name = request.args.get('doctor')
    date = request.args.get('date')
    
    if not (doctor_name and date):
        return jsonify({'error': 'Doctor and date parameters are required.'}), 400
    
    conn = get_db_connection()
    booked_slots = conn.execute(
        "SELECT time FROM appointments WHERE doctor_name=? AND date=? AND status IN ('pending', 'checked_in') ORDER BY time", 
        (doctor_name, date)
    ).fetchall()
    conn.close()
    
    occupied_times = [slot['time'] for slot in booked_slots]
    standard_times = [
        '09:00', '09:30', '10:00', '10:30', '11:00', '11:30', 
        '14:00', '14:30', '15:00', '15:30', '16:00', '16:30'
    ]
    available_times = [time for time in standard_times if time not in occupied_times]
    
    return jsonify({'available_times': available_times})

# -------------------------
# Patient Dashboard
# -------------------------
@app.route('/patient_dashboard')
@login_required
def patient_dashboard():
    user_id = session.get('user_id')
    conn = get_db_connection()
    
    # Get appointments
    appts = conn.execute(
        'SELECT * FROM appointments WHERE patient_name=? ORDER BY date, time',
        (session['full_name'],)
    ).fetchall()
    
    # Get prescription count
    prescription_count = conn.execute(
        'SELECT COUNT(*) as count FROM prescriptions WHERE patient_id = ?',
        (user_id,)
    ).fetchone()['count']
    
    # Get medical records count
    medical_records_count = conn.execute(
        'SELECT COUNT(*) as count FROM medical_records WHERE patient_id = ?',
        (user_id,)
    ).fetchone()['count']
    
    # Get unrated completed appointments for rating popup
    unrated_appointments_rows = conn.execute(
        "SELECT * FROM appointments WHERE patient_name=? AND status='completed' AND (rating IS NULL OR rating = '')",
        (session['full_name'],)
    ).fetchall()
    unrated_appointments = [dict(row) for row in unrated_appointments_rows]
    
    # Process appointments into Upcoming and Recent
    upcoming_appointments = []
    past_appointments = []
    
    current_time = datetime.now()
    
    for row in appts:
        appt = dict(row)
        
        # Enhanced Status Logic for 'checked_in'
        if appt['status'] == 'checked_in':
            # Check if this patient is the first one checked in for this doctor
            first_checked_in = conn.execute('''
                SELECT id FROM appointments 
                WHERE doctor_id = ? AND date = ? AND status='checked_in'
                ORDER BY queue_number ASC LIMIT 1
            ''', (appt['doctor_id'], appt['date'])).fetchone()
            
            if first_checked_in and first_checked_in['id'] == appt['id']:
                 appt['status_display'] = 'In Consultation'
                 appt['status_class'] = 'info' # Blue/Info style
            else:
                 appt['status_display'] = 'Waiting in Lobby'
                 appt['status_class'] = 'warning' # Yellow/Warning style
        else:
            # Default display
            appt['status_display'] = appt['status'].replace('_', ' ').capitalize()
            appt['status_class'] = 'info' if appt['status'] == 'checked_in' else ('warning' if appt['status'] == 'pending' else 'secondary')

        # Status based partitioning
        if appt['status'] in ['pending', 'confirmed', 'checked_in']:
            upcoming_appointments.append(appt)
        else:
            past_appointments.append(appt)
            
    # Sort upcoming by date ascending (closest first) - already sorted from SQL
    
    # Sort past by date descending (most recent first)
    past_appointments.sort(key=lambda x: (x['date'], x['time']), reverse=True)
    
    conn.close()
    
    user = get_current_user()
    return render_template('patient_dashboard.html', 
                         appointments=appts,
                         upcoming_appointments=upcoming_appointments,
                         past_appointments=past_appointments,
                         user=user,
                         prescription_count=prescription_count,
                         medical_records_count=medical_records_count,
                         unrated_appointments=unrated_appointments)

@app.route('/submit_rating', methods=['POST'])
@login_required
def submit_rating():
    appt_id = request.form.get('appointment_id')
    rating = request.form.get('rating')
    review = request.form.get('review')
    
    if not appt_id or not rating:
        flash('Please provide a rating.', 'error')
        return redirect(url_for('patient_dashboard'))
    
    conn = get_db_connection()
    try:
        # Verify appointment belongs to user and is completed
        appt = conn.execute(
            "SELECT id FROM appointments WHERE id=? AND patient_name=? AND status='completed'", 
            (appt_id, session['full_name'])
        ).fetchone()
        
        if not appt:
            flash('Invalid appointment.', 'error')
        else:
            conn.execute('UPDATE appointments SET rating=?, review=? WHERE id=?', (rating, review, appt_id))
            conn.commit()
            flash('Thank you for your feedback!', 'success')
            
    except Exception as e:
        conn.rollback()
        flash(f'Error submitting rating: {str(e)}', 'error')
    finally:
        conn.close()
        
    return redirect(url_for('patient_dashboard'))

# -------------------------
# Medical History
# -------------------------
@app.route('/patient/medical_history')
@login_required
def medical_history():
    user_id = session.get('user_id')
    conn = get_db_connection()
    
    # Get all medical records for the patient
    records = conn.execute('''
        SELECT mr.*, u.full_name as doctor_name, c.name as clinic_name
        FROM medical_records mr
        JOIN users u ON mr.doctor_id = u.id
        JOIN clinics c ON mr.clinic_id = c.id
        WHERE mr.patient_id = ?
        ORDER BY mr.created_at DESC
    ''', (user_id,)).fetchall()
    
    # Prepare vital signs data for chart
    vital_signs_data = None
    if records:
        dates = []
        systolic = []
        diastolic = []
        weight = []
        
        for record in reversed(list(records)):  # Chronological order for chart
            if record['created_at']:
                dates.append(record['created_at'][:10])
            if record['blood_pressure']:
                bp_parts = record['blood_pressure'].split('/')
                if len(bp_parts) == 2:
                    systolic.append(int(bp_parts[0]))
                    diastolic.append(int(bp_parts[1]))
            if record['weight']:
                weight_val = record['weight'].replace('kg', '').strip()
                try:
                    weight.append(float(weight_val))
                except:
                    weight.append(None)
        
        if dates:
            vital_signs_data = {
                'dates': dates,
                'systolic': systolic,
                'diastolic': diastolic,
                'weight': weight
            }
    
    conn.close()
    user = get_current_user()
    return render_template('medical_history.html', records=records, vital_signs_data=vital_signs_data, user=user)

# -------------------------
# Prescriptions
# -------------------------
@app.route('/patient/prescriptions')
@login_required
def prescriptions():
    user_id = session.get('user_id')
    filter_status = request.args.get('filter', 'all')
    
    conn = get_db_connection()
    
    # Build query based on filter
    query = '''
        SELECT p.*, u.full_name as doctor_name, c.name as clinic_name
        FROM prescriptions p
        JOIN users u ON p.doctor_id = u.id
        JOIN clinics c ON p.clinic_id = c.id
        WHERE p.patient_id = ?
    '''
    
    if filter_status == 'active':
        query += " AND p.status = 'active'"
    elif filter_status == 'completed':
        query += " AND p.status = 'completed'"
    
    query += ' ORDER BY p.prescribed_date DESC'
    
    prescriptions_list = conn.execute(query, (user_id,)).fetchall()
    
    # Calculate stats
    active_count = conn.execute('SELECT COUNT(*) as count FROM prescriptions WHERE patient_id = ? AND status = "active"', (user_id,)).fetchone()['count']
    completed_count = conn.execute('SELECT COUNT(*) as count FROM prescriptions WHERE patient_id = ? AND status = "completed"', (user_id,)).fetchone()['count']
    
    # Calculate progress for active prescriptions
    from datetime import datetime, timedelta
    prescriptions_with_progress = []
    for rx in prescriptions_list:
        rx_dict = dict(rx)
        if rx['status'] == 'active' and rx['end_date']:
            try:
                start_date = datetime.strptime(rx['prescribed_date'], '%Y-%m-%d')
                end_date = datetime.strptime(rx['end_date'], '%Y-%m-%d')
                today = datetime.now()
                
                total_days = (end_date - start_date).days
                days_passed = (today - start_date).days
                days_left = (end_date - today).days
                
                if total_days > 0:
                    progress = min(100, max(0, (days_passed / total_days) * 100))
                else:
                    progress = 100
                
                rx_dict['progress'] = int(progress)
                rx_dict['days_left'] = max(0, days_left)
            except:
                rx_dict['progress'] = 0
                rx_dict['days_left'] = 0
        else:
            rx_dict['progress'] = 100 if rx['status'] == 'completed' else 0
            rx_dict['days_left'] = 0
        
        prescriptions_with_progress.append(rx_dict)
    
    conn.close()
    user = get_current_user()
    return render_template('prescriptions.html', 
                         prescriptions=prescriptions_with_progress,
                         active_count=active_count,
                         completed_count=completed_count,
                         filter_status=filter_status,
                         user=user)

# -------------------------
# Edit Appointment
# -------------------------
@app.route('/edit_appointment/<int:appointment_id>', methods=['GET', 'POST'])
@login_required
def edit_appointment(appointment_id):
    conn = get_db_connection()
    appt = conn.execute('SELECT * FROM appointments WHERE id=?', (appointment_id,)).fetchone()
 
    if appt is None:
        conn.close()
        flash("Appointment not found.", "error")
        return redirect(url_for('patient_dashboard'))
 
    # Check if user has permission to edit this appointment
    # Using robust string comparison for names
    patient_name = appt['patient_name'].strip().lower() if appt['patient_name'] else ''
    current_user_name = session.get('full_name', '').strip().lower()
    
    if patient_name != current_user_name and session.get('role') not in ('admin', 'reception'):
        conn.close()
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for('patient_dashboard'))

    if request.method == 'POST':
        doctor_id = request.form.get('doctor_id', '').strip()
        clinic_id = request.form.get('clinic_id', '').strip()
        date = request.form.get('date', '').strip()
        time = request.form.get('time', '').strip()
        reason = request.form.get('reason', '').strip()
 
        if not (doctor_id and clinic_id and date and time):
            flash("All required fields must be filled.", "error")
            conn.close()
            return redirect(url_for('edit_appointment', appointment_id=appointment_id))

        # Get doctor and clinic names
        doctor = conn.execute('SELECT full_name FROM users WHERE id=?', (doctor_id,)).fetchone()
        clinic = conn.execute('SELECT name FROM clinics WHERE id=?', (clinic_id,)).fetchone()
        
        if not (doctor and clinic):
            flash("Invalid doctor or clinic selection.", "error")
            conn.close()
            return redirect(url_for('edit_appointment', appointment_id=appointment_id))

        # Check for time slot conflicts
        conflict = conn.execute(
            "SELECT id FROM appointments WHERE doctor_id=? AND clinic_id=? AND date=? AND time=? AND status IN ('pending', 'checked_in') AND id!=?",
            (doctor_id, clinic_id, date, time, appointment_id)
        ).fetchone()

        if conflict:
            conn.close()
            flash("The selected time slot is already booked. Please choose another time.", "error")
            return redirect(url_for('edit_appointment', appointment_id=appointment_id))
 
        conn.execute(
            "UPDATE appointments SET doctor_name=?, doctor_id=?, clinic_name=?, clinic_id=?, date=?, time=?, reason=? WHERE id=?",
            (doctor['full_name'], doctor_id, clinic['name'], clinic_id, date, time, reason, appointment_id)
        )
        conn.commit()
        conn.close()
        flash("Appointment updated successfully.", "success")
        return redirect(url_for('patient_dashboard'))
 
    # GET request - show edit form
    clinics = conn.execute('SELECT id, name, address FROM clinics ORDER BY name').fetchall()
    conn.close()
    
    user = get_current_user()
    return render_template('edit_appointment.html', appt=appt, clinics=clinics, user=user)

@app.route('/cancel_appointment/<int:appointment_id>', methods=['POST'])
@login_required
def cancel_appointment(appointment_id):
    conn = get_db_connection()
    appt = conn.execute('SELECT * FROM appointments WHERE id=?', (appointment_id,)).fetchone()
    
    if appt is None:
        conn.close()
        return jsonify({'success': False, 'message': 'Appointment not found'}), 404
    
    # Check if user has permission to cancel this appointment
    patient_name = appt['patient_name'].strip().lower() if appt['patient_name'] else ''
    current_user_name = session.get('full_name', '').strip().lower()
    
    if patient_name != current_user_name and session.get('role') not in ('admin', 'reception'):
        conn.close()
        return jsonify({'success': False, 'message': 'You can only cancel your own appointments'}), 403
    
    # Update appointment status to cancelled
    conn.execute(
        "UPDATE appointments SET status='cancelled' WHERE id=?",
        (appointment_id,)
    )
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Appointment cancelled successfully'})


# -------------------------
# Reception Dashboard
# -------------------------
@app.route('/reception')
@login_required
@role_required('reception', 'admin')
def reception():
    today = datetime.now().date().isoformat()
    conn = get_db_connection()
    
    user = get_current_user()
    if user:
        user = dict(user)
    
    # Check for clinic restriction
    clinic_name_filter = None
    if user['role'] == 'reception' and user.get('clinic_id'):
        clinic_row = conn.execute("SELECT name FROM clinics WHERE id=?", (user['clinic_id'],)).fetchone()
        if clinic_row:
            clinic_name_filter = clinic_row[0]
            
    # Base query parts
    base_where = "date=?"
    params = [today]
    
    if clinic_name_filter:
        base_where += " AND clinic_name=?"
        params.append(clinic_name_filter)
        
    # Calculate statistics using dynamic query
    total_in_queue = conn.execute(
        f"SELECT COUNT(*) FROM appointments WHERE {base_where} AND status IN ('pending', 'checked_in')",
        params
    ).fetchone()[0]
    
    checked_in = conn.execute(
        f"SELECT COUNT(*) FROM appointments WHERE {base_where} AND status='checked_in'",
        params
    ).fetchone()[0]
    
    waiting = conn.execute(
        f"SELECT COUNT(*) FROM appointments WHERE {base_where} AND status='pending'",
        params
    ).fetchone()[0]
    
    # Calculate average wait time (simplified - based on time slots)
    avg_wait_time = 18  # Default placeholder
    
    stats = {
        'total_in_queue': total_in_queue,
        'checked_in': checked_in,
        'waiting': waiting,
        'avg_wait_time': avg_wait_time
    }
    
    conn.close()
    return render_template('reception.html', stats=stats, user=user)

# -------------------------
# Queue Management
# -------------------------
@app.route('/queue_management')
@login_required
@role_required('reception', 'admin')
def queue_management():
    today = datetime.now().date().isoformat()
    # DEBUG: Print tracking
    print(f"--- DEBUG: Queue Management Access ---")
    print(f"Date: {today}")
    
    conn = get_db_connection()
    
    user = get_current_user()
    if user:
        user = dict(user)
        print(f"User: {user['username']} (ID: {user['id']}, Role: {user['role']}, ClinicID: {user.get('clinic_id')})")
    
    # Check for clinic restriction
    clinic_name_filter = None
    if user['role'] == 'reception' and user.get('clinic_id'):
        clinic_row = conn.execute("SELECT name FROM clinics WHERE id=?", (user['clinic_id'],)).fetchone()
        if clinic_row:
            clinic_name_filter = clinic_row[0]
            print(f"Clinic Filter Applied: '{clinic_name_filter}'")
        else:
            print(f"Clinic Filter Error: User has clinic_id {user['clinic_id']} but no name found.")
            
    # Base where clause
    base_where = "date=?"
    params = [today]
    if clinic_name_filter:
        base_where += " AND clinic_name=?"
        params.append(clinic_name_filter)

    print(f"Query WHERE: {base_where}")
    print(f"Query Params: {params}")

    # Get now serving (first checked-in patient)
    now_serving = conn.execute(
        f"SELECT * FROM appointments WHERE {base_where} AND status='checked_in' ORDER BY queue_number LIMIT 1",
        params
    ).fetchone()
    if now_serving:
        print(f"Now Serving Found: {dict(now_serving)}")
    else:
        print("Now Serving: None")
    
    # Add room info if patient is being served
    if now_serving:
        now_serving = dict(now_serving)
        q_num = now_serving.get('queue_number') or 0
        now_serving['queue_number'] = q_num
        
        # Fetch Room Number from Doctor's association
        doc_assoc = conn.execute(
            "SELECT room_number FROM clinic_staff_association WHERE user_id=? AND clinic_id=? AND role='doctor'",
            (now_serving['doctor_id'], now_serving['clinic_id'])
        ).fetchone()
        
        if doc_assoc and doc_assoc['room_number']:
            now_serving['room'] = doc_assoc['room_number']
        else:
            now_serving['room'] = f"Room {(q_num % 5) + 1}" # Fallback

    
    # Get in progress (checked-in patients)
    in_progress_raw = conn.execute(
        f"SELECT * FROM appointments WHERE {base_where} AND status='checked_in' ORDER BY queue_number",
        params
    ).fetchall()
    
    in_progress = []
    occupied_doctors = set() # Track which doctors already have a patient in their room
    
    for appt in in_progress_raw:
        appt_dict = dict(appt)
        q_num = appt_dict.get('queue_number') or 0
        appt_dict['queue_number'] = q_num
        doc_id = appt_dict['doctor_id']
        
        # Check if doctor is already busy with a previous patient in this list
        if doc_id not in occupied_doctors:
            # Doctor is free -> Assign Room
            occupied_doctors.add(doc_id)
            
            # Fetch Room Number
            doc_assoc = conn.execute(
                "SELECT room_number FROM clinic_staff_association WHERE user_id=? AND clinic_id=? AND role='doctor'",
                (doc_id, appt_dict['clinic_id'])
            ).fetchone()
            
            if doc_assoc and doc_assoc['room_number']:
                appt_dict['room'] = doc_assoc['room_number']
            else:
                appt_dict['room'] = f"Room {(q_num % 5) + 1}"
        else:
            # Doctor is busy -> Sending to Waiting Area
            appt_dict['room'] = "Waiting Area"
            
        in_progress.append(appt_dict)
    
    # Get up next (pending patients)
    up_next_raw = conn.execute(
        f"SELECT * FROM appointments WHERE {base_where} AND status='pending' ORDER BY time LIMIT 10",
        params
    ).fetchall()
    print(f"Up Next Count: {len(up_next_raw)}")
    
    up_next = []
    for idx, appt in enumerate(up_next_raw, 1):
        appt_dict = dict(appt)
        appt_dict['queue_number'] = idx + 5  # Placeholder queue numbers
        appt_dict['wait_time'] = idx * 5  # Estimated wait time
        up_next.append(appt_dict)
    
    # Get all appointments for today (for the list view) with phone numbers
    all_appointments = conn.execute(
        f"""
        SELECT a.*, u.phone as patient_phone 
        FROM appointments a
        LEFT JOIN users u ON a.patient_name = u.full_name
        WHERE {base_where} 
        ORDER BY a.time
        """,
        params
    ).fetchall()
    print(f"Total Appointments List: {len(all_appointments)}")
    
    conn.close()
    return render_template('queue_management.html', 
                         now_serving=now_serving,
                         in_progress=in_progress,
                         up_next=up_next,
                         all_appointments=all_appointments,
                         user=user)
 
@app.route('/checkin/<int:appointment_id>')
@login_required
@role_required('reception', 'admin')
def checkin(appointment_id):
    conn = get_db_connection()
    appt = conn.execute("SELECT doctor_name, date FROM appointments WHERE id=?", (appointment_id,)).fetchone()
    if appt:
        max_queue = conn.execute(
            "SELECT MAX(queue_number) FROM appointments WHERE doctor_name=? AND date=?",
            (appt['doctor_name'], appt['date'])
        ).fetchone()[0]
        
        new_queue = (max_queue or 0) + 1
        
        conn.execute(
            "UPDATE appointments SET status='checked_in', queue_number=? WHERE id=?", 
            (new_queue, appointment_id)
        )
        conn.commit()
        flash(f"Patient checked in successfully. Queue Number: {new_queue}", "success")
    else:
        flash("Appointment not found.", "error")

    conn.close()
    return redirect(url_for('reception'))
 
@app.route('/cancel/<int:appointment_id>')
@login_required
@role_required('reception', 'admin')
def cancel(appointment_id):
    conn = get_db_connection()
    conn.execute("UPDATE appointments SET status='cancelled' WHERE id=?", (appointment_id,))
    conn.commit()
    conn.close()
    flash("Appointment cancelled.", "info")
    return redirect(url_for('reception'))
 
# -------------------------
# Doctor Dashboard
# -------------------------
@app.route('/doctor_dashboard')
@login_required
@role_required('doctor')
def doctor_dashboard():
    user = get_current_user()
    today = datetime.now().date().isoformat()
    conn = get_db_connection()
    
    # Get today's appointments for this doctor
    appointments_raw = conn.execute(
        "SELECT * FROM appointments WHERE doctor_id=? AND date=? ORDER BY time",
        (user['id'], today)
    ).fetchall()
    
    # Process appointments to identify Current vs Waiting
    appointments = []
    found_current = False
    
    for appt in appointments_raw:
        a = dict(appt)
        # Default flags
        a['is_current'] = False
        a['is_waiting'] = False
        
        if a['status'] == 'checked_in':
            if not found_current:
                # First checked-in patient is the one in the room
                a['is_current'] = True
                found_current = True
            else:
                # Subsequent checked-in patients are waiting
                a['is_waiting'] = True
                
        appointments.append(a)
    
    # Calculate stats
    pending_count = conn.execute(
        "SELECT COUNT(*) FROM appointments WHERE doctor_id=? AND date=? AND status='pending'",
        (user['id'], today)
    ).fetchone()[0]
    
    # All-time stats (more meaningful than today's completed)
    total_patients = conn.execute(
        "SELECT COUNT(DISTINCT patient_id) FROM prescriptions WHERE doctor_id=?",
        (user['id'],)
    ).fetchone()[0]
    
    total_prescriptions = conn.execute(
        "SELECT COUNT(*) FROM prescriptions WHERE doctor_id=?",
        (user['id'],)
    ).fetchone()[0]
    
    conn.close()
    return render_template('doctor_dashboard.html', 
                         user=user, 
                         appointments=appointments,
                         pending_count=pending_count,
                         total_patients=total_patients,
                         total_prescriptions=total_prescriptions)

@app.route('/complete_appointment/<int:appointment_id>', methods=['POST'])
@login_required
@role_required('doctor')
def complete_appointment(appointment_id):
    conn = get_db_connection()
    user = get_current_user()
    
    # Verify appointment exists and belongs to this doctor
    appt = conn.execute(
        "SELECT * FROM appointments WHERE id=? AND doctor_id=?", 
        (appointment_id, user['id'])
    ).fetchone()
    
    if not appt:
        conn.close()
        flash("Appointment not found or access denied.", "error")
        return redirect(url_for('doctor_dashboard'))
        
    # Update status
    conn.execute(
        "UPDATE appointments SET status='completed' WHERE id=?",
        (appointment_id,)
    )
    conn.commit()
    conn.close()
    
    flash("Appointment marked as completed.", "success")
    return redirect(url_for('doctor_dashboard'))

# -------------------------
# Doctor Prescriptions
# -------------------------
# Doctor Patients
# -------------------------
@app.route('/doctor/patients')
@login_required
@role_required('doctor')
def doctor_patients():
    user = get_current_user()
    doctor_id = user['id']
    
    conn = get_db_connection()
    
    # Get all unique patients this doctor has treated OR has appointments with
    # Using UNION to get patients from appointments, medical_records, and prescriptions
    patients_query = '''
        SELECT DISTINCT u.id, u.full_name, u.email
        FROM users u
        WHERE u.id IN (
            SELECT DISTINCT patient_id FROM medical_records WHERE doctor_id = ?
            UNION
            SELECT DISTINCT patient_id FROM prescriptions WHERE doctor_id = ?
            UNION
            SELECT DISTINCT u2.id 
            FROM appointments a 
            JOIN users u2 ON a.patient_name = u2.full_name 
            WHERE a.doctor_id = ?
        )
        ORDER BY u.full_name
    '''
    
    patients_list = conn.execute(patients_query, (doctor_id, doctor_id, doctor_id)).fetchall()
    
    # For each patient, get their stats
    patients_with_stats = []
    for patient in patients_list:
        patient_id = patient['id']
        
        # Get last visit date from medical records
        last_visit = conn.execute(
            'SELECT MAX(created_at) as last_visit FROM medical_records WHERE patient_id = ? AND doctor_id = ?',
            (patient_id, doctor_id)
        ).fetchone()['last_visit']
        
        # Count appointments
        total_appointments = conn.execute(
            'SELECT COUNT(*) as count FROM appointments WHERE patient_name = (SELECT full_name FROM users WHERE id = ?) AND doctor_id = ?',
            (patient_id, doctor_id)
        ).fetchone()['count']
        
        # Count medical records (Global)
        medical_records = conn.execute(
            'SELECT COUNT(*) as count FROM medical_records WHERE patient_id = ?',
            (patient_id,)
        ).fetchone()['count']
        
        # Count active prescriptions (Global)
        active_prescriptions = conn.execute(
            'SELECT COUNT(*) as count FROM prescriptions WHERE patient_id = ? AND status = "active"',
            (patient_id,)
        ).fetchone()['count']
        
        patients_with_stats.append({
            'id': patient['id'],
            'full_name': patient['full_name'],
            'email': patient['email'],
            'last_visit': last_visit[:10] if last_visit else None,
            'total_appointments': total_appointments,
            'medical_records': medical_records,
            'active_prescriptions': active_prescriptions
        })
    
    # Calculate totals
    total_records = conn.execute(
        'SELECT COUNT(*) as count FROM medical_records WHERE doctor_id = ?',
        (doctor_id,)
    ).fetchone()['count']
    
    total_prescriptions = conn.execute(
        'SELECT COUNT(*) as count FROM prescriptions WHERE doctor_id = ?',
        (doctor_id,)
    ).fetchone()['count']
    
    conn.close()
    
    return render_template('doctor_patients.html',
                         user=user,
                         patients=patients_with_stats,
                         total_records=total_records,
                         total_prescriptions=total_prescriptions)

@app.route('/doctor/patient/<int:patient_id>')
@login_required
@role_required('doctor')
def doctor_patient_details(patient_id):
    conn = get_db_connection()
    user = get_current_user()
    
    # Get patient details
    patient = conn.execute('SELECT * FROM users WHERE id = ?', (patient_id,)).fetchone()
    if not patient:
        conn.close()
        flash('Patient not found', 'error')
        return redirect(url_for('doctor_patients'))
        
    # Get medical records (Global)
    medical_records = conn.execute('''
        SELECT mr.*, u.full_name as doctor_name
        FROM medical_records mr
        JOIN users u ON mr.doctor_id = u.id
        WHERE mr.patient_id = ?
        ORDER BY mr.created_at DESC
    ''', (patient_id,)).fetchall()
    
    # Get prescriptions (Global)
    prescriptions = conn.execute('''
        SELECT p.*, u.full_name as doctor_name
        FROM prescriptions p
        JOIN users u ON p.doctor_id = u.id
        WHERE p.patient_id = ? AND p.status = 'active'
        ORDER BY p.created_at DESC
    ''', (patient_id,)).fetchall()
    
    conn.close()
    
    return render_template('doctor_patient_details.html',
                         user=user,
                         patient=patient,
                         medical_records=medical_records,
                         prescriptions=prescriptions)

# -------------------------
# Doctor Prescriptions
@app.route('/doctor/prescriptions')
@login_required
@role_required('doctor')
def doctor_prescriptions():
    user = get_current_user()
    doctor_id = user['id']
    filter_status = request.args.get('filter', 'all')
    
    conn = get_db_connection()
    
    # Build query based on filter
    query = '''
        SELECT p.*, u.full_name as patient_name, u.email as patient_email, c.name as clinic_name
        FROM prescriptions p
        JOIN users u ON p.patient_id = u.id
        JOIN clinics c ON p.clinic_id = c.id
        WHERE p.doctor_id = ?
    '''
    
    if filter_status == 'active':
        query += " AND p.status = 'active'"
    elif filter_status == 'completed':
        query += " AND p.status = 'completed'"
    
    query += ' ORDER BY p.prescribed_date DESC'
    
    prescriptions_list = conn.execute(query, (doctor_id,)).fetchall()
    
    # Calculate stats
    active_count = conn.execute(
        'SELECT COUNT(*) as count FROM prescriptions WHERE doctor_id = ? AND status = "active"',
        (doctor_id,)
    ).fetchone()['count']
    
    # Count unique patients
    patient_count = conn.execute(
        'SELECT COUNT(DISTINCT patient_id) as count FROM prescriptions WHERE doctor_id = ?',
        (doctor_id,)
    ).fetchone()['count']
    
    conn.close()
    
    return render_template('doctor_prescriptions.html',
                         user=user,
                         prescriptions=prescriptions_list,
                         active_count=active_count,
                         patient_count=patient_count,
                         filter_status=filter_status)


# -------------------------
# Doctor Add Prescription
# -------------------------
@app.route('/doctor/prescription/add', methods=['GET', 'POST'])
@login_required
@role_required('doctor')
def doctor_add_prescription():
    user = get_current_user()
    doctor_id = user['id']
    
    conn = get_db_connection()
    
    # Get list of patients this doctor has treated
    # Get list of patients this doctor has treated OR has appointments with
    patients_query = '''
        SELECT DISTINCT u.id, u.full_name, u.email
        FROM users u
        WHERE u.id IN (
            SELECT DISTINCT patient_id FROM medical_records WHERE doctor_id = ?
            UNION
            SELECT DISTINCT patient_id FROM prescriptions WHERE doctor_id = ?
            UNION
            SELECT DISTINCT u2.id 
            FROM appointments a 
            JOIN users u2 ON a.patient_name = u2.full_name 
            WHERE a.doctor_id = ?
        )
        ORDER BY u.full_name
    '''
    patients_list = conn.execute(patients_query, (doctor_id, doctor_id, doctor_id)).fetchall()
    
    if request.method == 'POST':
        # Get form data
        patient_id = request.form.get('patient_id')
        medication_name = request.form.get('medication_name')
        dosage = request.form.get('dosage')
        frequency = request.form.get('frequency')
        duration = request.form.get('duration')
        instructions = request.form.get('instructions', '')
        status = request.form.get('status', 'active')
        end_date = request.form.get('end_date', None)
        
        # Validation
        if not all([patient_id, medication_name, dosage, frequency, duration]):
            conn.close()
            return render_template('doctor_add_prescription.html',
                                 user=user,
                                 patients=patients_list,
                                 error='Please fill in all required fields')
        
        # Get clinic_id from doctor's association
        clinic_id = conn.execute(
            'SELECT clinic_id FROM doctor_clinic WHERE doctor_id = ? LIMIT 1',
            (doctor_id,)
        ).fetchone()
        
        if not clinic_id:
            conn.close()
            return render_template('doctor_add_prescription.html',
                                 user=user,
                                 patients=patients_list,
                                 error='No clinic association found')
        
        clinic_id = clinic_id['clinic_id']
        
        # Insert prescription
        from datetime import datetime
        prescribed_date = datetime.now().date().isoformat()
        
        conn.execute('''
            INSERT INTO prescriptions 
            (patient_id, doctor_id, clinic_id, medication_name, dosage, frequency, 
             duration, instructions, status, prescribed_date, end_date, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ''', (patient_id, doctor_id, clinic_id, medication_name, dosage, frequency,
              duration, instructions, status, prescribed_date, end_date))
        
        conn.commit()
        conn.close()
        
        # Redirect to prescriptions list with success message
        return redirect(url_for('doctor_prescriptions'))
    
    # GET request - show form
    selected_patient_id = request.args.get('patient_id', None)
    conn.close()
    
    return render_template('doctor_add_prescription.html',
                         user=user,
                         patients=patients_list,
                         selected_patient_id=selected_patient_id,
                         success=False,
                         error=None)

# -------------------------
# Admin Dashboard
# -------------------------
@app.route('/admin')
@login_required
@role_required('admin', 'clinic_admin')
def admin():
    conn = get_db_connection()
    total = conn.execute('SELECT COUNT(*) FROM appointments').fetchone()[0]
    today = datetime.now().date().isoformat()
    today_count = conn.execute('SELECT COUNT(*) FROM appointments WHERE date=?', (today,)).fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM appointments WHERE status='pending'").fetchone()[0]
    checked_in = conn.execute("SELECT COUNT(*) FROM appointments WHERE status='checked_in'").fetchone()[0]
    completed = conn.execute("SELECT COUNT(*) FROM appointments WHERE status='completed'").fetchone()[0]
    cancelled = conn.execute("SELECT COUNT(*) FROM appointments WHERE status='cancelled'").fetchone()[0]
    no_show = conn.execute("SELECT COUNT(*) FROM appointments WHERE status='no_show'").fetchone()[0]
    no_show = conn.execute("SELECT COUNT(*) FROM appointments WHERE status='no_show'").fetchone()[0]
    
    # Get 5 most recent appointments
    recent_appointments = conn.execute("SELECT * FROM appointments ORDER BY date DESC, time DESC LIMIT 5").fetchall()
    
    # Get clinics for status card
    clinics = conn.execute("SELECT * FROM clinics").fetchall()
    
    conn.close()
    stats = {'total': total, 'today': today_count, 'pending': pending, 'checked_in': checked_in, 'completed': completed, 'cancelled': cancelled, 'no_show': no_show}
    user = get_current_user()
    return render_template('admin.html', stats=stats, recent_appointments=recent_appointments, clinics=clinics, user=user)

# -------------------------
# Manage Users (Admin Only)
# -------------------------
@app.route('/manage_users')
@login_required
@role_required('admin', 'clinic_admin')
def manage_users():
    conn = get_db_connection()
    
    # Get filter parameter
    role_filter = request.args.get('role', 'all')
    
    # Build query based on filter
    if role_filter == 'all':
        users = conn.execute('SELECT id, username, full_name, email, phone, role FROM users ORDER BY role, full_name').fetchall()
    else:
        users = conn.execute('SELECT id, username, full_name, email, phone, role FROM users WHERE role=? ORDER BY full_name', (role_filter,)).fetchall()
    
    # Get user counts by role
    total_users = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    doctors_count = conn.execute("SELECT COUNT(*) FROM users WHERE role='doctor'").fetchone()[0]
    patients_count = conn.execute("SELECT COUNT(*) FROM users WHERE role='patient'").fetchone()[0]
    receptionists_count = conn.execute("SELECT COUNT(*) FROM users WHERE role='reception'").fetchone()[0]
    admins_count = conn.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0]
    clinic_admins_count = conn.execute("SELECT COUNT(*) FROM users WHERE role='clinic_admin'").fetchone()[0]
    
    conn.close()
    
    user = get_current_user()
    return render_template('manage_users.html', 
                         users=users,
                         user=user,
                         role_filter=role_filter,
                         total_users=total_users,
                         doctors_count=doctors_count,
                         patients_count=patients_count,
                         receptionists_count=receptionists_count,
                         clinic_admins_count=clinic_admins_count)

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
@role_required('admin')
def delete_user(user_id):
    current_user_id = session.get('user_id')
    if user_id == current_user_id:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('manage_users'))
        
    conn = get_db_connection()
    try:
        # Check if user exists
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if not user:
            flash('User not found.', 'error')
            return redirect(url_for('manage_users'))
            
        # Delete user
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        # You might want to delete related data here or rely on foreign key cascade if configured
        conn.commit()
        flash(f"User {user['full_name']} deleted successfully.", 'success')
    except Exception as e:
        conn.rollback()
        flash(f"Error deleting user: {str(e)}", 'error')
    finally:
        conn.close()
        
    return redirect(url_for('manage_users'))

@app.route('/edit_user/<int:user_id>', methods=['POST'])
@login_required
@role_required('admin')
def edit_user(user_id):
    conn = get_db_connection()
    try:
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        role = request.form.get('role')
        
        # Validation could be added here
        
        conn.execute('''
            UPDATE users 
            SET full_name = ?, email = ?, phone = ?, role = ?
            WHERE id = ?
        ''', (full_name, email, phone, role, user_id))
        conn.commit()
        flash('User updated successfully.', 'success')
    except Exception as e:
        conn.rollback()
        flash(f"Error updating user: {str(e)}", 'error')
    finally:
        conn.close()
        
    return redirect(url_for('manage_users'))
 
# -------------------------
# Manage Clinics (Admin Only)
# -------------------------
@app.route('/manage_clinics')
@login_required
@role_required('admin', 'clinic_admin')
def manage_clinics():
    conn = get_db_connection()
    clinics = conn.execute('SELECT id, name, address, phone, status FROM clinics ORDER BY name').fetchall()
    conn.close()
    user = get_current_user()
    return render_template('manage_clinics.html', clinics=clinics, user=user)

@app.route('/add_clinic', methods=['POST'])
@login_required
@role_required('admin', 'clinic_admin')
def add_clinic():
    name = request.form.get('name')
    address = request.form.get('address')
    phone = request.form.get('phone')
    
    # Clinic admin user details
    admin_username = request.form.get('admin_username')
    admin_fullname = request.form.get('admin_fullname')
    admin_email = request.form.get('admin_email')
    admin_password = request.form.get('admin_password')
    admin_confirm_password = request.form.get('admin_confirm_password')
    
    # Validate clinic details
    if not name or not address:
        flash('Clinic name and address are required', 'error')
        return redirect(url_for('manage_clinics'))
    
    # Validate admin user details
    if not admin_username or not admin_fullname or not admin_password:
        flash('Admin username, full name, and password are required', 'error')
        return redirect(url_for('manage_clinics'))
    
    # Validate password match
    if admin_password != admin_confirm_password:
        flash('Admin passwords do not match', 'error')
        return redirect(url_for('manage_clinics'))
    
    # Validate password length
    if len(admin_password) < 6:
        flash('Admin password must be at least 6 characters long', 'error')
        return redirect(url_for('manage_clinics'))
    
    conn = get_db_connection()
    
    try:
        # Check if username already exists
        existing_user = conn.execute('SELECT id FROM users WHERE username = ?', (admin_username,)).fetchone()
        if existing_user:
            flash(f'Username "{admin_username}" already exists. Please choose a different username.', 'error')
            return redirect(url_for('manage_clinics'))
        
        # Check if clinic name already exists
        existing_clinic = conn.execute('SELECT id FROM clinics WHERE name = ?', (name,)).fetchone()
        if existing_clinic:
            flash(f'Clinic "{name}" already exists', 'error')
            return redirect(url_for('manage_clinics'))
        
        # Insert clinic
        cursor = conn.execute('INSERT INTO clinics (name, address, phone, status) VALUES (?, ?, ?, ?)',
                     (name, address, phone, 'active'))
        clinic_id = cursor.lastrowid
        
        # Hash the password
        hashed_password = generate_password_hash(admin_password)
        
        # Insert clinic admin user
        conn.execute('''INSERT INTO users (username, full_name, email, phone, password, role, clinic_id) 
                        VALUES (?, ?, ?, ?, ?, ?, ?)''',
                     (admin_username, admin_fullname, admin_email, '', hashed_password, 'clinic_admin', clinic_id))
        
        conn.commit()
        flash(f'Clinic "{name}" and admin user "{admin_username}" added successfully', 'success')
    
    except Exception as e:
        conn.rollback()
        flash(f'Error adding clinic: {str(e)}', 'error')
    
    finally:
        conn.close()
    
    return redirect(url_for('manage_clinics'))

@app.route('/edit_clinic/<int:clinic_id>', methods=['POST'])
@login_required
@role_required('admin', 'clinic_admin')
def edit_clinic(clinic_id):
    name = request.form.get('name')
    address = request.form.get('address')
    phone = request.form.get('phone')
    
    if not name or not address:
        flash('Clinic name and address are required', 'error')
        return redirect(url_for('manage_clinics'))
    
    conn = get_db_connection()
    conn.execute('UPDATE clinics SET name=?, address=?, phone=? WHERE id=?',
                 (name, address, phone, clinic_id))
    conn.commit()
    conn.close()
    
    flash('Clinic updated successfully', 'success')
    return redirect(url_for('manage_clinics'))

@app.route('/delete_clinic/<int:clinic_id>', methods=['POST'])
@login_required
@role_required('admin', 'clinic_admin')
def delete_clinic(clinic_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM clinics WHERE id=?', (clinic_id,))
    conn.commit()
    conn.close()
    
    flash('Clinic deleted successfully', 'success')
    return redirect(url_for('manage_clinics'))

@app.route('/toggle_clinic_status/<int:clinic_id>', methods=['POST'])
@login_required
@role_required('admin', 'clinic_admin')
def toggle_clinic_status(clinic_id):
    conn = get_db_connection()
    clinic = conn.execute('SELECT status FROM clinics WHERE id=?', (clinic_id,)).fetchone()
    
    if clinic:
        new_status = 'inactive' if clinic['status'] == 'active' else 'active'
        conn.execute('UPDATE clinics SET status=? WHERE id=?', (new_status, clinic_id))
        conn.commit()
        flash(f'Clinic status changed to {new_status}', 'success')
    
    conn.close()
    return redirect(url_for('manage_clinics'))

# -------------------------
# Analytics Pages (Admin Only)
# -------------------------
@app.route('/analytics1')
@login_required
@role_required('admin', 'clinic_admin')
def analytics1():
    conn = get_db_connection()
    
    # 1. Appointments for Selected Range (Strict Timeline)
    time_range = request.args.get('range', 'week')
    days_to_show = 30 if time_range == 'month' else 7
    
    today = datetime.now().date()
    dates = []
    counts = []
    
    for i in range(days_to_show - 1, -1, -1): # days_to_show days ago up to today
        current_date = today - timedelta(days=i)
        date_str = current_date.isoformat()
        dates.append(date_str)
        
        # Get count for this specific date
        count = conn.execute('SELECT COUNT(*) FROM appointments WHERE date = ?', (date_str,)).fetchone()[0]
        counts.append(count)
    
    # 2. Status Breakdown
    status_counts = conn.execute('''
        SELECT status, COUNT(*) as count 
        FROM appointments 
        GROUP BY status
    ''').fetchall()
    
    status_data = {row['status']: row['count'] for row in status_counts}
    
    # 3. Total Users (Mocking growth since we don't have created_at)
    total_users = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    
    conn.close()
    
    user = get_current_user()
    return render_template('analytics1.html', 
                         user=user,
                         dates=dates,
                         counts=counts,
                         status_data=status_data,
                         total_users=total_users,
                         time_range=time_range)

@app.route('/analytics2')
@login_required
@role_required('admin', 'clinic_admin')
def analytics2():
    conn = get_db_connection()
    
    # 1. Fetch Doctors and their Clinics
    # We join users -> clinic_staff_association -> clinics
    # This gives us a row for each doctor-clinic pair.
    query = '''
        SELECT u.full_name as doctor_name, c.name as clinic_name
        FROM users u
        JOIN clinic_staff_association csa ON u.id = csa.user_id
        JOIN clinics c ON csa.clinic_id = c.id
        WHERE u.role = 'doctor' AND csa.is_active = 1
        ORDER BY c.name, u.full_name
    '''
    
    doctor_clinic_pairs = conn.execute(query).fetchall()
    
    # Prepare data for analytics
    analytics_data = []
    
    # Lists for Charts
    chart_labels = [] # "Dr. Name - Clinic Name"
    chart_ratings = []
    chart_visits = []
    
    import random
    
    for row in doctor_clinic_pairs:
        doc_name = row['doctor_name']
        clinic_name = row['clinic_name']
        
        # Mock Data for this specific doctor-clinic pair
        # In a real app, you'd aggregate appointments where doctor_id=? AND clinic_id=?
        rating = round(random.uniform(3.5, 5.0), 1)
        visits = random.randint(20, 150)
        
        label = f"{doc_name} - {clinic_name}"
        
        analytics_data.append({
            'doctor': doc_name,
            'clinic': clinic_name,
            'rating': rating,
            'visits': visits,
            'label': label
        })
        
        chart_labels.append(label)
        chart_ratings.append(rating)
        chart_visits.append(visits)

    # 3. Clinic Performance (Aggregate mock data for radar chart)
    # Let's just group the above mock data by clinic to get realistic averages if we wanted,
    # but for now we can keep the simple clinic query for the radar chart or improve it.
    # Let's keep it consistent with the pairs.
    clinics = conn.execute('SELECT name FROM clinics').fetchall()
    clinic_radar_labels = [row['name'] for row in clinics]
    clinic_radar_scores = [round(random.uniform(4.0, 5.0), 1) for _ in clinic_radar_labels]
    
    conn.close()
    
    user = get_current_user()
    return render_template('analytics2.html', 
                         user=user,
                         analytics_data=analytics_data,
                         chart_labels=chart_labels,
                         chart_ratings=chart_ratings,
                         chart_visits=chart_visits,
                         clinic_radar_labels=clinic_radar_labels,
                         clinic_radar_scores=clinic_radar_scores)

@app.route('/analytics2/export')
@login_required
@role_required('admin', 'clinic_admin')
def export_doctor_ratings():
    conn = get_db_connection()
    
    # 1. Doctors and their appointment counts (as a proxy for volume)
    doctor_stats = conn.execute('''
        SELECT doctor_name, COUNT(*) as appt_count 
        FROM appointments 
        GROUP BY doctor_name
    ''').fetchall()
    
    doctors = [row['doctor_name'] for row in doctor_stats]
    appt_counts = [row['appt_count'] for row in doctor_stats]
    
    # 2. Mock Ratings (Random float between 3.5 and 5.0)
    import random
    ratings = [round(random.uniform(3.5, 5.0), 1) for _ in doctors]
    
    conn.close()
    
    # Create CSV
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Doctor Name', 'Rating', 'Patient Volume', 'Status'])
    
    for i in range(len(doctors)):
        cw.writerow([
            doctors[i],
            ratings[i],
            f"{appt_counts[i]} visits",
            "Top Rated"
        ])
        
    output = si.getvalue()
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=doctor_ratings_report.csv"})
 
# -------------------------
# Export CSV (Admin Only)
# -------------------------
@app.route('/export')
@login_required
@role_required('admin', 'clinic_admin')
def export_csv():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM appointments ORDER BY date, time").fetchall()
    conn.close()
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['id', 'patient_name', 'doctor_name', 'date', 'time', 'status'])
    for r in rows:
        cw.writerow([r['id'], r['patient_name'], r['doctor_name'], r['date'], r['time'], r['status']])
    output = si.getvalue()
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=appointments.csv"})
 
# -------------------------
# Queue Status API
# -------------------------
@app.route('/api/patient_queue_status')
@login_required
def patient_queue_status():
    today = datetime.now().date().isoformat()
    patient_name = session.get('full_name')
    
    print(f"DEBUG: Checking queue for {patient_name}")
    
    conn = get_db_connection()
    
    # Find user's next upcoming appointment (today or future)
    my_appt = conn.execute('''
        SELECT * FROM appointments 
        WHERE patient_name = ? AND date >= ? AND status IN ('pending', 'checked_in')
        ORDER BY date ASC, time ASC LIMIT 1
    ''', (patient_name, today)).fetchone()
    
    if not my_appt:
        print(f"DEBUG: No upcoming appointment found for {patient_name}")
        conn.close()
        return jsonify({'has_appointment': False})
        
    print(f"DEBUG: Found appointment on {my_appt['date']} with Dr. {my_appt['doctor_name']} at {my_appt['time']}")
    
    doctor_id = my_appt['doctor_id']
    my_date = my_appt['date']
    # Calculate how many people are ahead in the queue
    # Logic:
    # 1. Appointments with earlier TIME for the same doctor/date
    # 2. Status 'checked_in' or 'pending'
    
    # NEW LOGIC: Check if I am the one "In Consultation"
    # If I am checked_in AND I am the first one in the checked_in list, I am current.
    
    is_in_consultation = False
    status_text = "waiting"
    
    if my_appt['status'] == 'checked_in':
        # Get all checked in patients for this doctor sorted by queue number/time
        checked_in_patients = conn.execute('''
            SELECT * FROM appointments 
            WHERE doctor_id = ? AND date = ? AND status='checked_in'
            ORDER BY queue_number ASC
        ''', (doctor_id, my_date)).fetchall()
        
        if checked_in_patients:
            first_patient = checked_in_patients[0]
            if first_patient['patient_name'] == patient_name:
                is_in_consultation = True
                status_text = "consultation"
            else:
                status_text = "lobby"
    
    my_time = my_appt['time']
    # Calculate ahead count (people waiting before me)
    ahead_count = conn.execute('''
        SELECT COUNT(*) FROM appointments 
        WHERE doctor_id = ? AND date = ? 
        AND status IN ('pending', 'checked_in')
        AND time < ?
    ''', (doctor_id, my_date, my_time)).fetchone()[0]
    
    print(f"DEBUG: {ahead_count} people ahead. Status: {status_text}")
    
    conn.close()
    
    return jsonify({
        'has_appointment': True,
        'doctor_name': my_appt['doctor_name'],
        'ahead_count': ahead_count,
        'my_time': my_time,
        'appointment_date': my_date,
        'status': status_text, # 'waiting', 'lobby', 'consultation'
        'is_in_consultation': is_in_consultation
    })

# -------------------------
# Clinic Admin Dashboard
# -------------------------
@app.route('/clinic_admin_dashboard')
@login_required
@role_required('clinic_admin')
def clinic_admin_dashboard():
    clinic_id = session.get('clinic_id')
    if not clinic_id:
        flash('No clinic associated with your account', 'error')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    
    # Get clinic name
    clinic = conn.execute('SELECT name FROM clinics WHERE id = ?', (clinic_id,)).fetchone()
    clinic_name = clinic['name'] if clinic else 'Unknown Clinic'
    
    # Get today and tomorrow dates
    today = datetime.now().date().isoformat()
    tomorrow = (datetime.now().date() + timedelta(days=1)).isoformat()
    
    # Calculate statistics
    stats = {}
    
    # Today's appointments
    stats['today_appointments'] = conn.execute(
        'SELECT COUNT(*) FROM appointments WHERE clinic_id = ? AND date = ?',
        (clinic_id, today)
    ).fetchone()[0]
    
    # Tomorrow's appointments
    stats['tomorrow_appointments'] = conn.execute(
        'SELECT COUNT(*) FROM appointments WHERE clinic_id = ? AND date = ?',
        (clinic_id, tomorrow)
    ).fetchone()[0]
    
    # Total appointments
    stats['total_appointments'] = conn.execute(
        'SELECT COUNT(*) FROM appointments WHERE clinic_id = ?',
        (clinic_id,)
    ).fetchone()[0]
    
    # Total doctors (from clinic_staff_association)
    stats['total_doctors'] = conn.execute(
        "SELECT COUNT(DISTINCT user_id) FROM clinic_staff_association WHERE clinic_id = ? AND role = 'doctor' AND is_active = 1",
        (clinic_id,)
    ).fetchone()[0]
    
    # Total receptionists
    stats['total_receptionists'] = conn.execute(
        "SELECT COUNT(DISTINCT user_id) FROM clinic_staff_association WHERE clinic_id = ? AND role = 'reception' AND is_active = 1",
        (clinic_id,)
    ).fetchone()[0]
    
    # Total unique patients (who have appointments at this clinic)
    stats['total_patients'] = conn.execute(
        'SELECT COUNT(DISTINCT patient_name) FROM appointments WHERE clinic_id = ?',
        (clinic_id,)
    ).fetchone()[0]
    
    # Get appointments data for last 7 days (for chart)
    seven_days_ago = (datetime.now().date() - timedelta(days=6)).isoformat()
    appointments_by_date = conn.execute('''
        SELECT date, COUNT(*) as count 
        FROM appointments 
        WHERE clinic_id = ? AND date >= ? AND date <= ?
        GROUP BY date 
        ORDER BY date ASC
    ''', (clinic_id, seven_days_ago, today)).fetchall()
    
    # Create full 7-day range with 0 counts for missing dates
    dates = []
    counts = []
    for i in range(7):
        date = (datetime.now().date() - timedelta(days=6-i)).isoformat()
        dates.append(date)
        count = next((row['count'] for row in appointments_by_date if row['date'] == date), 0)
        counts.append(count)
    
    # Get status counts for pie chart
    status_counts_raw = conn.execute('''
        SELECT status, COUNT(*) as count 
        FROM appointments 
        WHERE clinic_id = ?
        GROUP BY status
    ''', (clinic_id,)).fetchall()
    
    status_counts = {row['status']: row['count'] for row in status_counts_raw}
    
    # Get recent appointments (last 10)
    recent_appointments = conn.execute('''
        SELECT * FROM appointments 
        WHERE clinic_id = ? 
        ORDER BY date DESC, time DESC 
        LIMIT 10
    ''', (clinic_id,)).fetchall()
    
    conn.close()
    
    chart_data = {
        'dates': dates,
        'counts': counts,
        'status_counts': status_counts
    }
    
    user = get_current_user()
    return render_template('clinic_admin_dashboard.html',
                         user=user,
                         clinic_name=clinic_name,
                         stats=stats,
                         chart_data=chart_data,
                         recent_appointments=recent_appointments)

# Clinic Admin - Doctors Management
@app.route('/clinic_admin/doctors')
@login_required
@role_required('clinic_admin')
def clinic_admin_doctors():
    clinic_id = session.get('clinic_id')
    if not clinic_id:
        flash('No clinic associated with your account', 'error')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    
    # Get clinic name
    clinic = conn.execute('SELECT name FROM clinics WHERE id = ?', (clinic_id,)).fetchone()
    clinic_name = clinic['name'] if clinic else 'Unknown Clinic'
    
    # Get all doctors associated with this clinic
    doctors = conn.execute('''
        SELECT u.id as user_id, u.full_name, u.email, u.phone, u.specialization, csa.is_active
        FROM users u
        JOIN clinic_staff_association csa ON u.id = csa.user_id
        WHERE csa.clinic_id = ? AND csa.role = 'doctor' AND u.role = 'doctor'
        ORDER BY u.full_name
    ''', (clinic_id,)).fetchall()
    
    # Get all doctors not yet assigned to this clinic
    available_doctors = conn.execute('''
        SELECT id, full_name, email, specialization
        FROM users
        WHERE role = 'doctor' 
        AND id NOT IN (
            SELECT user_id FROM clinic_staff_association 
            WHERE clinic_id = ? AND role = 'doctor'
        )
        ORDER BY full_name
    ''', (clinic_id,)).fetchall()
    
    conn.close()
    
    user = get_current_user()
    return render_template('clinic_admin_doctors.html',
                         user=user,
                         clinic_name=clinic_name,
                         doctors=doctors,
                         available_doctors=available_doctors)

@app.route('/clinic_admin/doctors/add', methods=['POST'])
@login_required
@role_required('clinic_admin')
def clinic_admin_add_doctor():
    clinic_id = session.get('clinic_id')
    if not clinic_id:
        flash('No clinic associated with your account', 'error')
        return redirect(url_for('home'))
    
    add_type = request.form.get('add_type', 'existing')
    conn = get_db_connection()
    
    try:
        if add_type == 'new':
            # Create new doctor
            username = request.form.get('new_username', '').strip()
            full_name = request.form.get('new_full_name', '').strip()
            email = request.form.get('new_email', '').strip()
            phone = request.form.get('new_phone', '').strip()
            specialization = request.form.get('new_specialization', '').strip()
            password = request.form.get('new_password', '').strip()
            confirm_password = request.form.get('new_confirm_password', '').strip()
            
            # Validation
            if not all([username, full_name, email, specialization, password]):
                flash('All required fields must be filled', 'error')
                return redirect(url_for('clinic_admin_doctors'))
            
            if password != confirm_password:
                flash('Passwords do not match', 'error')
                return redirect(url_for('clinic_admin_doctors'))
            
            if len(password) < 6:
                flash('Password must be at least 6 characters', 'error')
                return redirect(url_for('clinic_admin_doctors'))
            
            # Check if username or email already exists
            existing_user = conn.execute(
                'SELECT id FROM users WHERE username = ? OR email = ?',
                (username, email)
            ).fetchone()
            
            if existing_user:
                flash('Username or email already exists', 'error')
                return redirect(url_for('clinic_admin_doctors'))
            
            # Create the doctor user
            hashed_password = generate_password_hash(password)
            cursor = conn.execute('''
                INSERT INTO users (username, full_name, email, phone, password, role, specialization)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (username, full_name, email, phone, hashed_password, 'doctor', specialization))
            
            doctor_id = cursor.lastrowid
            
            # Associate with clinic
            conn.execute(
                'INSERT INTO clinic_staff_association (user_id, clinic_id, role, is_active) VALUES (?, ?, ?, ?)',
                (doctor_id, clinic_id, 'doctor', 1)
            )
            
            conn.commit()
            flash(f'Successfully created and added Dr. {full_name} to the clinic', 'success')
            
        else:
            # Add existing doctor
            doctor_id = request.form.get('doctor_id')
            if not doctor_id:
                flash('Please select a doctor', 'error')
                return redirect(url_for('clinic_admin_doctors'))
            
            # Check if doctor exists and is actually a doctor
            doctor = conn.execute('SELECT id, full_name FROM users WHERE id = ? AND role = "doctor"', (doctor_id,)).fetchone()
            if not doctor:
                flash('Invalid doctor selected', 'error')
                return redirect(url_for('clinic_admin_doctors'))
            
            # Check if already assigned
            existing = conn.execute(
                'SELECT id FROM clinic_staff_association WHERE user_id = ? AND clinic_id = ? AND role = "doctor"',
                (doctor_id, clinic_id)
            ).fetchone()
            
            if existing:
                flash(f'{doctor["full_name"]} is already assigned to this clinic', 'info')
            else:
                conn.execute(
                    'INSERT INTO clinic_staff_association (user_id, clinic_id, role, is_active) VALUES (?, ?, ?, ?)',
                    (doctor_id, clinic_id, 'doctor', 1)
                )
                conn.commit()
                flash(f'Successfully added {doctor["full_name"]} to the clinic', 'success')
                
    except Exception as e:
        conn.rollback()
        flash(f'Error adding doctor: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('clinic_admin_doctors'))

@app.route('/clinic_admin/doctors/shifts/<int:user_id>', methods=['POST'])
@login_required
@role_required('clinic_admin')
def clinic_admin_save_doctor_shifts(user_id):
    clinic_id = session.get('clinic_id')
    if not clinic_id:
        flash('No clinic associated with your account', 'error')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    try:
        # Verify doctor is assigned to this clinic
        association = conn.execute(
            'SELECT id FROM clinic_staff_association WHERE user_id = ? AND clinic_id = ? AND role = "doctor"',
            (user_id, clinic_id)
        ).fetchone()
        
        if not association:
            flash('Doctor not found in this clinic', 'error')
            return redirect(url_for('clinic_admin_doctors'))
        
        # Delete existing shifts for this doctor at this clinic
        conn.execute('DELETE FROM staff_shifts WHERE user_id = ? AND clinic_id = ?', (user_id, clinic_id))
        
        # Insert new shifts
        days = request.form.getlist('days')
        for day in days:
            start_time = request.form.get(f'start_{day}')
            end_time = request.form.get(f'end_{day}')
            
            if start_time and end_time:
                conn.execute('''
                    INSERT INTO staff_shifts (user_id, clinic_id, day_of_week, start_time, end_time, is_active)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, clinic_id, day, start_time, end_time, 1))
        
        conn.commit()
        flash('Shifts updated successfully', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error updating shifts: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('clinic_admin_doctors'))

@app.route('/clinic_admin/doctors/shifts/<int:user_id>/get')
@login_required
@role_required('clinic_admin')
def clinic_admin_get_doctor_shifts(user_id):
    clinic_id = session.get('clinic_id')
    if not clinic_id:
        return jsonify({'error': 'No clinic associated'}), 403
    
    conn = get_db_connection()
    shifts = conn.execute('''
        SELECT day_of_week, start_time, end_time
        FROM staff_shifts
        WHERE user_id = ? AND clinic_id = ? AND is_active = 1
        ORDER BY 
            CASE day_of_week
                WHEN 'Monday' THEN 1
                WHEN 'Tuesday' THEN 2
                WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4
                WHEN 'Friday' THEN 5
                WHEN 'Saturday' THEN 6
                WHEN 'Sunday' THEN 7
            END
    ''', (user_id, clinic_id)).fetchall()
    conn.close()
    
    return jsonify({'shifts': [dict(shift) for shift in shifts]})

@app.route('/clinic_admin/doctors/remove/<int:user_id>', methods=['POST'])
@login_required
@role_required('clinic_admin')
def clinic_admin_remove_doctor(user_id):
    clinic_id = session.get('clinic_id')
    if not clinic_id:
        flash('No clinic associated with your account', 'error')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    try:
        # Get doctor name for flash message
        doctor = conn.execute('SELECT full_name FROM users WHERE id = ?', (user_id,)).fetchone()
        
        # Delete shifts first (foreign key constraint)
        conn.execute('DELETE FROM staff_shifts WHERE user_id = ? AND clinic_id = ?', (user_id, clinic_id))
        
        # Delete association
        conn.execute(
            'DELETE FROM clinic_staff_association WHERE user_id = ? AND clinic_id = ? AND role = "doctor"',
            (user_id, clinic_id)
        )
        
        conn.commit()
        if doctor:
            flash(f'Successfully removed {doctor["full_name"]} from the clinic', 'success')
        else:
            flash('Doctor removed from clinic', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error removing doctor: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('clinic_admin_doctors'))

# Clinic Admin - Receptionists Management
@app.route('/clinic_admin/receptionists')
@login_required
@role_required('clinic_admin')
def clinic_admin_receptionists():
    clinic_id = session.get('clinic_id')
    if not clinic_id:
        flash('No clinic associated with your account', 'error')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    clinic = conn.execute('SELECT name FROM clinics WHERE id = ?', (clinic_id,)).fetchone()
    clinic_name = clinic['name'] if clinic else 'Unknown Clinic'
    
    receptionists = conn.execute('''
        SELECT u.id as user_id, u.full_name, u.email, u.phone, csa.is_active
        FROM users u
        JOIN clinic_staff_association csa ON u.id = csa.user_id
        WHERE csa.clinic_id = ? AND csa.role = 'reception' AND u.role = 'reception'
        ORDER BY u.full_name
    ''', (clinic_id,)).fetchall()
    
    available_receptionists = conn.execute('''
        SELECT id, full_name, email
        FROM users
        WHERE role = 'reception' 
        AND id NOT IN (
            SELECT user_id FROM clinic_staff_association 
            WHERE clinic_id = ? AND role = 'reception'
        )
        ORDER BY full_name
    ''', (clinic_id,)).fetchall()
    
    conn.close()
    user = get_current_user()
    return render_template('clinic_admin_receptionists.html',
                         user=user, clinic_name=clinic_name,
                         receptionists=receptionists,
                         available_receptionists=available_receptionists)

@app.route('/clinic_admin/receptionists/edit/<int:user_id>', methods=['POST'])
@login_required
@role_required('clinic_admin')
def clinic_admin_edit_receptionist(user_id):
    clinic_id = session.get('clinic_id')
    if not clinic_id:
        return redirect(url_for('home'))
        
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    
    conn = get_db_connection()
    try:
        # Verify user belongs to this clinic as receptionist
        association = conn.execute('''
            SELECT 1 FROM clinic_staff_association 
            WHERE user_id = ? AND clinic_id = ? AND role = 'reception'
        ''', (user_id, clinic_id)).fetchone()
        
        if association:
            conn.execute('''
                UPDATE users 
                SET full_name = ?, email = ?, phone = ?
                WHERE id = ?
            ''', (full_name, email, phone, user_id))
            conn.commit()
            flash('Receptionist details updated successfully', 'success')
        else:
            flash('Receptionist not found or not associated with this clinic', 'error')
            
    except Exception as e:
        conn.rollback()
        flash(f'Error updating receptionist: {str(e)}', 'error')
    finally:
        conn.close()
        
    return redirect(url_for('clinic_admin_receptionists'))

@app.route('/clinic_admin/receptionists/add', methods=['POST'])
@login_required
@role_required('clinic_admin')
def clinic_admin_add_receptionist():
    clinic_id = session.get('clinic_id')
    if not clinic_id:
        flash('No clinic associated with your account', 'error')
        return redirect(url_for('home'))
    
    add_type = request.form.get('add_type', 'existing')
    conn = get_db_connection()
    
    try:
        if add_type == 'new':
            # Create new receptionist
            username = request.form.get('new_username', '').strip()
            full_name = request.form.get('new_full_name', '').strip()
            email = request.form.get('new_email', '').strip()
            phone = request.form.get('new_phone', '').strip()
            password = request.form.get('new_password', '').strip()
            confirm_password = request.form.get('new_confirm_password', '').strip()
            
            # Validation
            if not all([username, full_name, email, phone, password]):
                flash('All required fields must be filled', 'error')
                return redirect(url_for('clinic_admin_receptionists'))
            
            if password != confirm_password:
                flash('Passwords do not match', 'error')
                return redirect(url_for('clinic_admin_receptionists'))
            
            if len(password) < 6:
                flash('Password must be at least 6 characters', 'error')
                return redirect(url_for('clinic_admin_receptionists'))
            
            # Check if username or email already exists
            existing_user = conn.execute(
                'SELECT id FROM users WHERE username = ? OR email = ?',
                (username, email)
            ).fetchone()
            
            if existing_user:
                flash('Username or email already exists', 'error')
                return redirect(url_for('clinic_admin_receptionists'))
            
            # Create the receptionist user
            hashed_password = generate_password_hash(password)
            cursor = conn.execute('''
                INSERT INTO users (username, full_name, email, phone, password, role)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, full_name, email, phone, hashed_password, 'reception'))
            
            receptionist_id = cursor.lastrowid
            
            # Associate with clinic
            conn.execute(
                'INSERT INTO clinic_staff_association (user_id, clinic_id, role, is_active) VALUES (?, ?, ?, ?)',
                (receptionist_id, clinic_id, 'reception', 1)
            )
            
            conn.commit()
            flash(f'Successfully created and added {full_name} to the clinic', 'success')
            
        else:
            # Add existing receptionist
            receptionist_id = request.form.get('receptionist_id')
            if not receptionist_id:
                flash('Please select a receptionist', 'error')
                return redirect(url_for('clinic_admin_receptionists'))
            
            receptionist = conn.execute('SELECT id, full_name FROM users WHERE id = ? AND role = "reception"', (receptionist_id,)).fetchone()
            if not receptionist:
                flash('Invalid receptionist selected', 'error')
                return redirect(url_for('clinic_admin_receptionists'))
            
            existing = conn.execute(
                'SELECT id FROM clinic_staff_association WHERE user_id = ? AND clinic_id = ? AND role = "reception"',
                (receptionist_id, clinic_id)
            ).fetchone()
            
            if existing:
                flash(f'{receptionist["full_name"]} is already assigned to this clinic', 'info')
            else:
                conn.execute(
                    'INSERT INTO clinic_staff_association (user_id, clinic_id, role, is_active) VALUES (?, ?, ?, ?)',
                    (receptionist_id, clinic_id, 'reception', 1)
                )
                conn.commit()
                flash(f'Successfully added {receptionist["full_name"]} to the clinic', 'success')
                
    except Exception as e:
        conn.rollback()
        flash(f'Error adding receptionist: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('clinic_admin_receptionists'))

@app.route('/clinic_admin/receptionists/shifts/<int:user_id>', methods=['POST'])
@login_required
@role_required('clinic_admin')
def clinic_admin_save_receptionist_shifts(user_id):
    clinic_id = session.get('clinic_id')
    if not clinic_id:
        flash('No clinic associated with your account', 'error')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    try:
        association = conn.execute(
            'SELECT id FROM clinic_staff_association WHERE user_id = ? AND clinic_id = ? AND role = "reception"',
            (user_id, clinic_id)
        ).fetchone()
        
        if not association:
            flash('Receptionist not found in this clinic', 'error')
            return redirect(url_for('clinic_admin_receptionists'))
        
        conn.execute('DELETE FROM staff_shifts WHERE user_id = ? AND clinic_id = ?', (user_id, clinic_id))
        
        days = request.form.getlist('days')
        for day in days:
            start_time = request.form.get(f'start_{day}')
            end_time = request.form.get(f'end_{day}')
            
            if start_time and end_time:
                conn.execute('''
                    INSERT INTO staff_shifts (user_id, clinic_id, day_of_week, start_time, end_time, is_active)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, clinic_id, day, start_time, end_time, 1))
        
        conn.commit()
        flash('Shifts updated successfully', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error updating shifts: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('clinic_admin_receptionists'))

@app.route('/clinic_admin/receptionists/shifts/<int:user_id>/get')
@login_required
@role_required('clinic_admin')
def clinic_admin_get_receptionist_shifts(user_id):
    clinic_id = session.get('clinic_id')
    if not clinic_id:
        return jsonify({'error': 'No clinic associated'}), 403
    
    conn = get_db_connection()
    shifts = conn.execute('''
        SELECT day_of_week, start_time, end_time
        FROM staff_shifts
        WHERE user_id = ? AND clinic_id = ? AND is_active = 1
        ORDER BY 
            CASE day_of_week
                WHEN 'Monday' THEN 1
                WHEN 'Tuesday' THEN 2
                WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4
                WHEN 'Friday' THEN 5
                WHEN 'Saturday' THEN 6
                WHEN 'Sunday' THEN 7
            END
    ''', (user_id, clinic_id)).fetchall()
    conn.close()
    
    return jsonify({'shifts': [dict(shift) for shift in shifts]})

@app.route('/clinic_admin/receptionists/remove/<int:user_id>', methods=['POST'])
@login_required
@role_required('clinic_admin')
def clinic_admin_remove_receptionist(user_id):
    clinic_id = session.get('clinic_id')
    if not clinic_id:
        flash('No clinic associated with your account', 'error')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    try:
        receptionist = conn.execute('SELECT full_name FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.execute('DELETE FROM staff_shifts WHERE user_id = ? AND clinic_id = ?', (user_id, clinic_id))
        conn.execute(
            'DELETE FROM clinic_staff_association WHERE user_id = ? AND clinic_id = ? AND role = "reception"',
            (user_id, clinic_id)
        )
        conn.commit()
        if receptionist:
            flash(f'Successfully removed {receptionist["full_name"]} from the clinic', 'success')
        else:
            flash('Receptionist removed from clinic', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error removing receptionist: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('clinic_admin_receptionists'))

# Clinic Admin - Patients
@app.route('/clinic_admin/patients')
@login_required
@role_required('clinic_admin')
def clinic_admin_patients():
    clinic_id = session.get('clinic_id')
    if not clinic_id:
        flash('No clinic associated with your account', 'error')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    clinic = conn.execute('SELECT name FROM clinics WHERE id = ?', (clinic_id,)).fetchone()
    clinic_name = clinic['name'] if clinic else 'Unknown Clinic'
    
    # Get unique patients with appointment stats
    patients = conn.execute('''
        SELECT 
            a.patient_name,
            u.email,
            u.phone,
            COUNT(a.id) as total_appointments,
            MAX(a.date) as last_visit
        FROM appointments a
        LEFT JOIN users u ON a.patient_name = u.full_name
        WHERE a.clinic_id = ?
        GROUP BY a.patient_name
        ORDER BY last_visit DESC
    ''', (clinic_id,)).fetchall()
    
    conn.close()
    user = get_current_user()
    return render_template('clinic_admin_patients.html',
                         user=user, clinic_name=clinic_name,
                         patients=patients)

# Clinic Admin - Appointments
@app.route('/clinic_admin/appointments')
@login_required
@role_required('clinic_admin')
def clinic_admin_appointments():
    clinic_id = session.get('clinic_id')
    if not clinic_id:
        flash('No clinic associated with your account', 'error')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    clinic = conn.execute('SELECT name FROM clinics WHERE id = ?', (clinic_id,)).fetchone()
    clinic_name = clinic['name'] if clinic else 'Unknown Clinic'
    
    # Get all doctors for filter dropdown
    doctors = conn.execute('''
        SELECT DISTINCT u.id as user_id, u.full_name
        FROM users u
        JOIN clinic_staff_association csa ON u.id = csa.user_id
        WHERE csa.clinic_id = ? AND csa.role = 'doctor'
        ORDER BY u.full_name
    ''', (clinic_id,)).fetchall()
    
    # Get filter parameters
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    doctor_id = request.args.get('doctor_id', '')
    status = request.args.get('status', '')
    
    # Build query with filters
    query = 'SELECT * FROM appointments WHERE clinic_id = ?'
    params = [clinic_id]
    
    if date_from:
        query += ' AND date >= ?'
        params.append(date_from)
    if date_to:
        query += ' AND date <= ?'
        params.append(date_to)
    if doctor_id:
        query += ' AND doctor_name = (SELECT full_name FROM users WHERE id = ?)'
        params.append(doctor_id)
    if status:
        query += ' AND status = ?'
        params.append(status)
    
    query += ' ORDER BY date DESC, time DESC LIMIT 100'
    
    appointments = conn.execute(query, params).fetchall()
    conn.close()
    
    filters = {
        'date_from': date_from,
        'date_to': date_to,
        'doctor_id': doctor_id,
        'status': status
    }
    
    user = get_current_user()
    return render_template('clinic_admin_appointments.html',
                         user=user, clinic_name=clinic_name,
                         appointments=appointments,
                         doctors=doctors,
                         filters=filters)

# -------------------------
# Edit Doctor Details (Clinic Admin)
# -------------------------
@app.route('/clinic_admin/doctors/edit/<int:user_id>', methods=['POST'])
@login_required
@role_required('clinic_admin')
def clinic_admin_edit_doctor(user_id):
    clinic_id = session.get('clinic_id')
    if not clinic_id:
        flash('No clinic associated with your account', 'error')
        return redirect(url_for('home'))
        
    conn = get_db_connection()
    try:
        # Verify doctor ownership via clinic association
        association = conn.execute(
            'SELECT id FROM clinic_staff_association WHERE user_id = ? AND clinic_id = ? AND role = "doctor"',
            (user_id, clinic_id)
        ).fetchone()
        
        if not association:
            flash('Doctor not found in this clinic', 'error')
            return redirect(url_for('clinic_admin_doctors'))
            
        # Get form data
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        specialization = request.form.get('specialization')
        
        # Update user details
        conn.execute('''
            UPDATE users 
            SET full_name = ?, email = ?, phone = ?, specialization = ? 
            WHERE id = ?
        ''', (full_name, email, phone, specialization, user_id))
        
        conn.commit()
        flash('Doctor details updated successfully', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Error updating details: {str(e)}', 'error')
        
    finally:
        conn.close()
        
    return redirect(url_for('clinic_admin_doctors'))

# -------------------------
# Run Flask
# -------------------------
# -------------------------
# Reschedule Appointment
# -------------------------
@app.route('/reschedule_appointment', methods=['POST'])
@login_required
@role_required('reception', 'admin')
def reschedule_appointment():
    appt_id = request.form.get('appointment_id')
    new_date = request.form.get('new_date')
    new_time = request.form.get('new_time')
    
    conn = get_db_connection()
    try:
        conn.execute('UPDATE appointments SET date=?, time=? WHERE id=?', (new_date, new_time, appt_id))
        conn.commit()
        flash('Appointment rescheduled successfully.', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error rescheduling: {str(e)}', 'error')
    finally:
        conn.close()
        
    return redirect(url_for('queue_management'))

if __name__ == '__main__':
    app.run(debug=True)
