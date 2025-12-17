import sqlite3
import random

DB_NAME = 'clinic.db'

def migrate():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("--- Adding room_number to clinic_staff_association ---")
    
    # Check if column exists
    cols = [top[1] for top in cursor.execute("PRAGMA table_info(clinic_staff_association)").fetchall()]
    if 'room_number' not in cols:
        print("Adding 'room_number' column...")
        cursor.execute("ALTER TABLE clinic_staff_association ADD COLUMN room_number TEXT")
    else:
        print("'room_number' column already exists.")

    # Backfill with random room numbers (1-5) for doctors
    print("Backfilling room numbers for doctors...")
    associations = cursor.execute("SELECT id, user_id, clinic_id FROM clinic_staff_association WHERE role='doctor'").fetchall()
    
    count = 0
    for assoc in associations:
        # Check if already has a room (if re-running)
        existing = cursor.execute("SELECT room_number FROM clinic_staff_association WHERE id=?", (assoc['id'],)).fetchone()[0]
        
        if not existing:
            # Assign random room 1-5
            room = f"Room {random.randint(1, 5)}"
            cursor.execute("UPDATE clinic_staff_association SET room_number=? WHERE id=?", (room, assoc['id']))
            count += 1
            
    print(f"Updated {count} doctor associations with room numbers.")
    
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
