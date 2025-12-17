import sqlite3
from werkzeug.security import generate_password_hash
import random

def migrate():
    print("--- Starting Doctor Separation Migration ---")
    conn = sqlite3.connect('clinic.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Fetch current doctors
    current_doctors = cursor.execute("SELECT id, full_name, username FROM users WHERE role='doctor'").fetchall()
    print(f"Current doctor count: {len(current_doctors)}")
    
    # We need 15 doctors total (3 clinics * 5 doctors)
    target_count = 15
    needed = target_count - len(current_doctors)
    
    new_doctor_ids = [d['id'] for d in current_doctors]
    
    # 2. Create new doctors if needed
    if needed > 0:
        print(f"Creating {needed} new doctors...")
        specializations = ['Cardiologist', 'Dermatologist', 'Pediatrician', 'Orthopedic', 'General Physician', 'Neurologist', 'Psychiatrist', 'ENT Specialist']
        
        for i in range(needed):
            num = len(current_doctors) + i + 1
            username = f'doctor_new_{num}'
            full_name = f'Dr. New Specialist {num}'
            email = f'doctor{num}@clinic.com'
            phone = f'99988877{i:02d}'
            password = generate_password_hash('12345')
            spec = random.choice(specializations)
            
            try:
                cursor.execute(
                    "INSERT INTO users (username, full_name, email, phone, password, role, specialization) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (username, full_name, email, phone, password, 'doctor', spec)
                )
                new_doctor_ids.append(cursor.lastrowid)
                print(f"  + Created {full_name} ({username})")
            except sqlite3.IntegrityError:
                print(f"  ! Skipped {username} (already exists)")
                # Try to find it to add to list if it existed but wasn't in first query (unlikely but safe)
                user = cursor.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
                if user and user['id'] not in new_doctor_ids:
                    new_doctor_ids.append(user['id'])

    print(f"Total Doctors Available: {len(new_doctor_ids)}")
    
    if len(new_doctor_ids) < 15:
        print("Warning: Still have less than 15 doctors. Proceeding with what we have.")

    # 3. Clear existing global assignments
    print("Clearing old doctor-clinic assignments...")
    cursor.execute("DELETE FROM doctor_clinics")
    print("  ✓ Cleared 'doctor_clinics' table")

    # 4. Re-assign strictly
    # Downtown: 1-5
    # Uptown: 6-10
    # West End: 11-15 (or rest)
    
    clinics = cursor.execute("SELECT id, name FROM clinics ORDER BY id").fetchall()
    if len(clinics) < 3:
        print("Error: Expected 3 clinics, found fewer.")
        return

    # Map clinic names to IDs for clarity
    clinic_map = {c['name']: c['id'] for c in clinics}
    downtown_id = clinic_map.get('Downtown Clinic', 1)
    uptown_id = clinic_map.get('Uptown Clinic', 2)
    west_end_id = clinic_map.get('West End Clinic', 3)
    
    assignments = []
    
    # helper to assign
    def assign(doc_id, clinic_id, c_name):
        assignments.append((doc_id, clinic_id))
        # Update user's main clinic_id for reference (optional but good for consistency)
        cursor.execute("UPDATE users SET clinic_id=? WHERE id=?", (clinic_id, doc_id))
    
    # Distribute
    # First 5 -> Downtown
    for doc_id in new_doctor_ids[:5]:
        assign(doc_id, downtown_id, "Downtown")
        
    # Next 5 -> Uptown
    for doc_id in new_doctor_ids[5:10]:
        assign(doc_id, uptown_id, "Uptown")
        
    # Rest -> West End
    for doc_id in new_doctor_ids[10:]:
        assign(doc_id, west_end_id, "West End")
        
    cursor.executemany("INSERT INTO doctor_clinics (doctor_id, clinic_id) VALUES (?, ?)", assignments)
    conn.commit()
    
    print("\n✓ Re-assignment Complete!")
    print("\nSummary:")
    print(f"  - Downtown Clinic: {len(new_doctor_ids[:5])} Doctors")
    print(f"  - Uptown Clinic:   {len(new_doctor_ids[5:10])} Doctors")
    print(f"  - West End Clinic: {len(new_doctor_ids[10:])} Doctors")
    
    conn.close()

if __name__ == "__main__":
    migrate()
