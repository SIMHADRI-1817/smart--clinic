import sqlite3

# Connect to database
conn = sqlite3.connect('clinic.db')
cursor = conn.cursor()

# Drop existing tables if they exist
print("Dropping existing tables...")
cursor.execute('DROP TABLE IF EXISTS prescriptions')
cursor.execute('DROP TABLE IF EXISTS medical_records')
print("✓ Tables dropped")

# Create medical_records table
cursor.execute('''
CREATE TABLE medical_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    doctor_id INTEGER NOT NULL,
    clinic_id INTEGER NOT NULL,
    appointment_id INTEGER,
    diagnosis TEXT NOT NULL,
    symptoms TEXT,
    notes TEXT,
    blood_pressure TEXT,
    temperature TEXT,
    weight TEXT,
    height TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

# Create prescriptions table
cursor.execute('''
CREATE TABLE prescriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    doctor_id INTEGER NOT NULL,
    clinic_id INTEGER NOT NULL,
    medical_record_id INTEGER,
    medication_name TEXT NOT NULL,
    dosage TEXT NOT NULL,
    frequency TEXT NOT NULL,
    duration TEXT NOT NULL,
    instructions TEXT,
    status TEXT DEFAULT 'active',
    prescribed_date DATE NOT NULL,
    end_date DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

conn.commit()
print("✓ Tables created successfully!")

# Insert sample medical records (patient_id=8 is Vikram, doctor_ids: 4=Amit Patel, 5=Ashish Kumar, 6=Neha Sharma)
sample_records = [
    (8, 4, 1, None, 'Hypertension', 'High blood pressure, headaches', 'Patient advised to reduce salt intake', '140/90', '98.6°F', '75 kg', '170 cm', '2024-11-20 10:30:00'),
    (8, 5, 2, None, 'Type 2 Diabetes', 'Increased thirst, frequent urination', 'Started on Metformin 500mg', '130/85', '98.4°F', '76 kg', '170 cm', '2024-11-15 14:00:00'),
    (8, 4, 1, None, 'Common Cold', 'Runny nose, cough, mild fever', 'Rest and fluids recommended', '120/80', '99.2°F', '75 kg', '170 cm', '2024-11-10 09:15:00'),
    (8, 6, 1, None, 'Migraine', 'Severe headache, sensitivity to light', 'Prescribed pain medication', '125/82', '98.5°F', '74 kg', '170 cm', '2024-11-05 16:45:00'),
    (8, 4, 1, None, 'Annual Checkup', 'No specific complaints', 'All vitals normal, continue healthy lifestyle', '118/78', '98.6°F', '74 kg', '170 cm', '2024-10-28 11:00:00'),
    (8, 5, 2, None, 'Gastritis', 'Stomach pain, acidity', 'Prescribed antacids, avoid spicy food', '122/80', '98.7°F', '75 kg', '170 cm', '2024-10-15 13:30:00'),
]

cursor.executemany('''
    INSERT INTO medical_records (patient_id, doctor_id, clinic_id, appointment_id, diagnosis, symptoms, notes, blood_pressure, temperature, weight, height, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', sample_records)

print(f"✓ Inserted {len(sample_records)} sample medical records")

# Insert sample prescriptions
sample_prescriptions = [
    (8, 4, 1, 1, 'Amlodipine', '5mg', 'Once daily', '30 days', 'Take in the morning with water', 'active', '2024-11-20', '2024-12-20'),
    (8, 4, 1, 1, 'Aspirin', '75mg', 'Once daily', '30 days', 'Take after breakfast', 'active', '2024-11-20', '2024-12-20'),
    (8, 5, 2, 2, 'Metformin', '500mg', 'Twice daily', 'Ongoing', 'Take with meals', 'active', '2024-11-15', None),
    (8, 4, 1, 3, 'Paracetamol', '500mg', 'Three times daily', '5 days', 'Take after meals', 'completed', '2024-11-10', '2024-11-15'),
    (8, 4, 1, 3, 'Cetirizine', '10mg', 'Once daily at night', '7 days', 'May cause drowsiness', 'completed', '2024-11-10', '2024-11-17'),
    (8, 6, 1, 4, 'Sumatriptan', '50mg', 'As needed', '10 tablets', 'Take at onset of migraine', 'active', '2024-11-05', '2024-12-05'),
    (8, 5, 2, 6, 'Omeprazole', '20mg', 'Once daily before breakfast', '14 days', 'Complete the full course', 'completed', '2024-10-15', '2024-10-29'),
    (8, 5, 2, 6, 'Antacid Syrup', '10ml', 'Three times daily', '7 days', 'Take 30 minutes before meals', 'completed', '2024-10-15', '2024-10-22'),
]

cursor.executemany('''
    INSERT INTO prescriptions (patient_id, doctor_id, clinic_id, medical_record_id, medication_name, dosage, frequency, duration, instructions, status, prescribed_date, end_date)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', sample_prescriptions)

print(f"✓ Inserted {len(sample_prescriptions)} sample prescriptions")

conn.commit()
conn.close()

print("\n✅ Database setup complete!")
print("   - medical_records table created")
print("   - prescriptions table created")
print("   - Sample data inserted")
