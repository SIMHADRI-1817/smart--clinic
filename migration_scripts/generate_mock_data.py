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

    print("--- Starting Comprehensive Mock Data Generation (2 weeks back to 2 weeks forward) ---")

    # 1. Fetch Basic Entities
    print("Fetching clinics and doctors...")
    clinics = cursor.execute("SELECT id, name FROM clinics").fetchall()
    doctors = cursor.execute("SELECT id, full_name, clinic_id FROM users WHERE role='doctor'").fetchall()
    
    if not clinics or not doctors:
        print("ERROR: No clinics or doctors found.")
        return

    # Create a map for clinic names for quick lookup
    clinic_map = {c['id']: c['name'] for c in clinics}
    
    # 2. Create Fake Patients
    print("Creating/Fetching patients...")
    # Get existing patients first
    existing_patients = cursor.execute("SELECT id, full_name FROM users WHERE role='patient'").fetchall()
    patients = [dict(p) for p in existing_patients]
    
    # Add 10 more to ensure we have enough diversity
    for _ in range(10): 
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
    today = datetime.now().date()
    now = datetime.now()
    appt_count = 0
    presc_count = 0

    # Date range: -14 days to +14 days
    for day_offset in range(-14, 15):
        current_date = today + timedelta(days=day_offset)
        date_str = current_date.isoformat()
        is_today = (current_date == today)
        is_past = (current_date < today)
        
        # For EACH doctor, generate appointments
        for doc in doctors:
            doc_data = dict(doc)
            # Skip if doctor has no clinic (though they should)
            if not doc_data['clinic_id']:
                continue
                
            clinic_id = doc_data['clinic_id']
            clinic_name = clinic_map.get(clinic_id, "Unknown Clinic")

            # 3-6 appointments per doctor per day
            daily_appts = random.randint(3, 6)
            
            # Generate sorted times for this doctor's day
            available_hours = list(range(9, 17)) # 9 AM to 5 PM
            random.shuffle(available_hours)
            selected_hours = available_hours[:daily_appts]
            selected_hours.sort()

            for hour in selected_hours:
                minute = random.choice(['00', '15', '30', '45'])
                time_str = f"{hour:02d}:{minute}"
                
                patient = random.choice(patients)
                
                # Smart Status Logic
                status = 'pending'
                
                if is_past:
                    # Past appointments are mostly completed
                    status = random.choices(
                        ['completed', 'completed', 'no_show', 'cancelled'], 
                        weights=[80, 5, 5, 10], k=1
                    )[0]
                elif is_today:
                    # Today: check time against NOW
                    appt_dt = datetime.combine(current_date, datetime.strptime(time_str, "%H:%M").time())
                    if appt_dt < now:
                        # Time has passed -> likely completed or currently happening
                        status = random.choices(
                            ['completed', 'in_progress', 'checked_in', 'no_show'],
                            weights=[60, 20, 10, 10], k=1
                        )[0]
                    else:
                        # Future time today -> pending
                        status = 'pending'
                else:
                    # Future dates
                    status = 'pending'

                cursor.execute('''
                    INSERT INTO appointments (patient_name, doctor_name, doctor_id, date, time, status, clinic_id, clinic_name, queue_number)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (patient['full_name'], doc_data['full_name'], doc_data['id'], date_str, time_str, status, clinic_id, clinic_name, random.randint(1, 50)))
                
                appt_id = cursor.lastrowid
                appt_count += 1
                
                # Generate Artifacts for Completed Appointments
                if status == 'completed':
                    # Prescription
                    if random.random() > 0.2: # 80% chance
                        med, dose, freq, dur = random.choice(MEDICATIONS)
                        cursor.execute('''
                            INSERT INTO prescriptions (patient_id, doctor_id, clinic_id, medication_name, dosage, frequency, duration, instructions, status, prescribed_date)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (patient['id'], doc_data['id'], clinic_id, med, dose, freq, dur, 'Take as directed', 'active', date_str))
                        presc_count += 1
                    
                    # Medical Record (Always)
                    systolic = random.randint(110, 140)
                    diastolic = random.randint(70, 90)
                    bp = f"{systolic}/{diastolic}"
                    weight = f"{random.randint(50, 90)} kg"
                    temp = f"{random.uniform(97, 99):.1f} F"
                    
                    try:
                        cursor.execute('''
                            INSERT INTO medical_records (patient_id, doctor_id, clinic_id, diagnosis, blood_pressure, weight, temperature, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (patient['id'], doc_data['id'], clinic_id, "Routine Checkup", bp, weight, temp, f"{date_str} {time_str}"))
                    except sqlite3.OperationalError:
                        pass

    conn.commit()
    conn.close()
    print(f"--- Done! Generated {appt_count} appointments and {presc_count} prescriptions. ---")

if __name__ == '__main__':
    create_mock_data()
