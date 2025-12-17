import sqlite3
import random
from datetime import datetime, timedelta

# Mock Data Config
FIRST_NAMES = ['Aarav', 'Vivaan', 'Aditya', 'Vihaan', 'Arjun', 'Sai', 'Reyansh', 'Ayaan', 'Krishna', 'Ishaan', 'Diya', 'Saanvi', 'Ananya', 'Aadhya', 'Pari', 'Myra', 'Ira', 'Riya', 'Aarohi', 'Meera']
LAST_NAMES = ['Patel', 'Sharma', 'Singh', 'Kumar', 'Gupta', 'Rao', 'Desai', 'Mehta', 'Joshi', 'Reddy', 'Nair', 'Malhotra', 'Verma', 'Bhat', 'Saxena']
DOMAINS = ['gmail.com', 'yahoo.com', 'outlook.com']

MEDICATIONS = [
    ('Paracetamol', '500mg', 'Twice daily', '5 days'),
    ('Amoxicillin', '500mg', 'Three times daily', '7 days'),
    ('Ibuprofen', '400mg', 'As needed', '3 days'),
    ('Cetirizine', '10mg', 'Once daily', '10 days'),
    ('Metformin', '500mg', 'Twice daily', 'Ongoing'),
    ('Amlodipine', '5mg', 'Once daily', 'Ongoing'),
    ('Pantoprazole', '40mg', 'Before breakfast', '14 days'),
    ('Azithromycin', '500mg', 'Once daily', '3 days')
]

def generate_phone():
    return f"+91 {random.randint(6000000000, 9999999999)}"

def create_mock_data():
    conn = sqlite3.connect('clinic.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("--- Starting Comprehensive Mock Data Generation ---")

    # 1. Fetch Basic Entities
    print("Fetching clinics and doctors...")
    clinics = cursor.execute("SELECT id, name FROM clinics").fetchall()
    doctors = cursor.execute("SELECT id, full_name, clinic_id FROM users WHERE role='doctor'").fetchall()
    
    if not clinics:
        print("ERROR: No clinics found.")
        return
    
    # Map doctors to clinics
    clinic_doctors = {c['id']: [] for c in clinics}
    all_doctors = []
    
    for d in doctors:
        doc_data = dict(d)
        all_doctors.append(doc_data)
        if doc_data['clinic_id']:
            if doc_data['clinic_id'] in clinic_doctors:
                clinic_doctors[doc_data['clinic_id']].append(doc_data)
    
    # 2. Create Fake Patients
    print("Creating/Fetching patients...")
    # Get existing patients first
    existing_patients = cursor.execute("SELECT id, full_name FROM users WHERE role='patient'").fetchall()
    patients = [dict(p) for p in existing_patients]
    
    # Add 15 more
    for _ in range(15): 
        fname = random.choice(FIRST_NAMES)
        lname = random.choice(LAST_NAMES)
        full_name = f"{fname} {lname}"
        username = f"{fname.lower()}.{lname.lower()}{random.randint(1, 9999)}"
        email = f"{username}@{random.choice(DOMAINS)}"
        password = "pbkdf2:sha256:260000$mockhash$mock"
        phone = generate_phone()
        
        # Check uniqueness
        exists = cursor.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if not exists:
            cursor.execute('''
                INSERT INTO users (username, full_name, email, phone, password, role) 
                VALUES (?, ?, ?, ?, ?, 'patient')
            ''', (username, full_name, email, phone, password))
            patients.append({'id': cursor.lastrowid, 'full_name': full_name})

    print(f"Total patients available: {len(patients)}")

    # 3. Create Appointments & Prescriptions
    print("Generating data for ALL clinics for last 30 days...")
    
    today = datetime.now().date()
    appt_count = 0
    presc_count = 0

    for i in range(30):
        current_date = today - timedelta(days=i)
        date_str = current_date.isoformat()
        
        for clinic in clinics:
            clinic_id = clinic['id']
            clinic_name = clinic['name']
            
            # Pick doctors for this clinic
            available_docs = clinic_doctors.get(clinic_id)
            if not available_docs:
                # If no doctor assigned, pick ANY doctor
                if all_doctors:
                    available_docs = all_doctors
                else:
                    continue # No doctors at all in system

            # 2-4 appointments per clinic per day
            daily_appts = random.randint(2, 4)
            
            for _ in range(daily_appts):
                patient = random.choice(patients)
                doctor = random.choice(available_docs)
                
                # Time
                hour = random.randint(9, 16)
                minute = random.choice(['00', '15', '30', '45'])
                time_str = f"{hour:02d}:{minute}"

                # Status
                if current_date < today:
                    status = random.choices(
                        ['completed', 'completed', 'no_show', 'cancelled'], 
                        weights=[70, 10, 10, 10], k=1
                    )[0]
                elif current_date == today:
                    status = random.choice(['checked_in', 'pending', 'completed'])
                else:
                    status = 'pending'

                cursor.execute('''
                    INSERT INTO appointments (patient_name, doctor_name, doctor_id, date, time, status, clinic_id, clinic_name, queue_number)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (patient['full_name'], doctor['full_name'], doctor['id'], date_str, time_str, status, clinic_id, clinic_name, random.randint(1, 50)))
                
                appt_id = cursor.lastrowid
                appt_count += 1
                
                # Add Prescription if completed
                if status == 'completed':
                    if random.random() > 0.3: # 70% chance of prescription
                        med, dose, freq, dur = random.choice(MEDICATIONS)
                        cursor.execute('''
                            INSERT INTO prescriptions (patient_id, doctor_id, clinic_id, medication_name, dosage, frequency, duration, instructions, status, prescribed_date)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (patient['id'], doctor['id'], clinic_id, med, dose, freq, dur, 'Take as directed', 'active', date_str))
                        presc_count += 1
                    
                    # Add Medical Record (Ensure 100% or similar chance for completed appts)
                    systolic = random.randint(110, 140)
                    diastolic = random.randint(70, 90)
                    bp = f"{systolic}/{diastolic}"
                    weight = f"{random.randint(50, 90)} kg"
                    temp = f"{random.uniform(97, 99):.1f} F"
                    
                    # Assuming table schema matches what we found/backfilled
                    try:
                        cursor.execute('''
                            INSERT INTO medical_records (patient_id, doctor_id, clinic_id, diagnosis, blood_pressure, weight, temperature, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (patient['id'], doctor['id'], clinic_id, "Routine Checkup", bp, weight, temp, f"{date_str} {time_str}"))
                    except sqlite3.OperationalError:
                        # Fallback if specific columns exist/don't exist - simplistic approach for now
                        pass

    conn.commit()
    conn.close()
    print(f"--- Done! Generated {appt_count} appointments and {presc_count} prescriptions. ---")

if __name__ == '__main__':
    create_mock_data()
