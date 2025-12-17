import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect('clinic.db')

# Drop old tables for fresh start
conn.execute("DROP TABLE IF EXISTS doctor_schedules")
conn.execute("DROP TABLE IF EXISTS doctor_clinics")
conn.execute("DROP TABLE IF EXISTS clinics")
conn.execute("DROP TABLE IF EXISTS appointments")
conn.execute("DROP TABLE IF EXISTS users")

# Create users table
conn.execute('''
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    password TEXT NOT NULL,
    role TEXT CHECK(role IN ('patient','reception','admin','doctor','clinic_admin')) NOT NULL,
    specialization TEXT,
    clinic_id INTEGER,
    FOREIGN KEY (clinic_id) REFERENCES clinics(id)
)
''')

# Create clinics table
conn.execute('''
CREATE TABLE clinics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    address TEXT,
    phone TEXT,
    status TEXT DEFAULT 'active'
)
''')

# Create doctor_clinics junction table (many-to-many)
conn.execute('''
CREATE TABLE doctor_clinics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id INTEGER NOT NULL,
    clinic_id INTEGER NOT NULL,
    FOREIGN KEY (doctor_id) REFERENCES users(id),
    FOREIGN KEY (clinic_id) REFERENCES clinics(id),
    UNIQUE(doctor_id, clinic_id)
)
''')

# Create appointments table with clinic information
conn.execute('''
CREATE TABLE appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_name TEXT NOT NULL,
    doctor_name TEXT NOT NULL,
    doctor_id INTEGER,
    clinic_name TEXT NOT NULL,
    clinic_id INTEGER,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    reason TEXT,
    status TEXT DEFAULT 'pending',
    queue_number INTEGER,
    FOREIGN KEY (doctor_id) REFERENCES users(id),
    FOREIGN KEY (clinic_id) REFERENCES clinics(id)
)
''')

# Add sample doctors
doctors = [
    ('dr_ashish', 'Dr. Ashish Kumar', 'ashish@clinic.com', '9876543210', generate_password_hash('12345'), 'doctor', 'Cardiologist'),
    ('dr_neha', 'Dr. Neha Sharma', 'neha@clinic.com', '9876543211', generate_password_hash('12345'), 'doctor', 'Dermatologist'),
    ('dr_ravi', 'Dr. Ravi Teja', 'ravi@clinic.com', '9876543212', generate_password_hash('12345'), 'doctor', 'Pediatrician'),
    ('dr_priya', 'Dr. Priya Singh', 'priya@clinic.com', '9876543213', generate_password_hash('12345'), 'doctor', 'Orthopedic'),
    ('dr_amit', 'Dr. Amit Patel', 'amit@clinic.com', '9876543214', generate_password_hash('12345'), 'doctor', 'General Physician')
]

conn.executemany('INSERT INTO users (username, full_name, email, phone, password, role, specialization) VALUES (?, ?, ?, ?, ?, ?, ?)', doctors)

# Add admin and receptionist
conn.execute("INSERT INTO users (username, full_name, email, phone, password, role) VALUES (?, ?, ?, ?, ?, ?)",
             ('admin', 'Admin User', 'admin@clinic.com', '9999999999', generate_password_hash('admin123'), 'admin'))
conn.execute("INSERT INTO users (username, full_name, email, phone, password, role) VALUES (?, ?, ?, ?, ?, ?)",
             ('reception', 'Reception Staff', 'reception@clinic.com', '9999999998', generate_password_hash('reception123'), 'reception'))

# Add sample clinics
clinics_data = [
    ('Downtown Clinic', '123 Main Street, Downtown', '555-0101'),
    ('Uptown Clinic', '456 Park Avenue, Uptown', '555-0102'),
    ('West End Clinic', '789 West End Road', '555-0103')
]

conn.executemany('INSERT INTO clinics (name, address, phone) VALUES (?, ?, ?)', clinics_data)

# Assign doctors to clinics
# Dr. Ashish Kumar -> Downtown, Uptown
# Dr. Neha Sharma -> Downtown, West End
# Dr. Ravi Teja -> Uptown, West End
# Dr. Priya Singh -> Downtown, Uptown, West End (all clinics)
# Dr. Amit Patel -> Downtown, West End

doctor_clinic_assignments = [
    (1, 1),  # Dr. Ashish -> Downtown
    (1, 2),  # Dr. Ashish -> Uptown
    (2, 1),  # Dr. Neha -> Downtown
    (2, 3),  # Dr. Neha -> West End
    (3, 2),  # Dr. Ravi -> Uptown
    (3, 3),  # Dr. Ravi -> West End
    (4, 1),  # Dr. Priya -> Downtown
    (4, 2),  # Dr. Priya -> Uptown
    (4, 3),  # Dr. Priya -> West End
    (5, 1),  # Dr. Amit -> Downtown
    (5, 3),  # Dr. Amit -> West End
]

conn.executemany('INSERT INTO doctor_clinics (doctor_id, clinic_id) VALUES (?, ?)', doctor_clinic_assignments)

conn.commit()
conn.close()
print("✅ Database initialized successfully with clinics and doctor assignments!")
print("\n📋 Summary:")
print("   - 5 Doctors added")
print("   - 3 Clinics created")
print("   - Doctor-Clinic assignments completed")
print("   - Admin & Reception accounts created")
print("\n🔐 Login Credentials:")
print("   Admin: admin / admin123")
print("   Reception: reception / reception123")
print("   Doctors: dr_ashish / 12345 (and similar for others)")