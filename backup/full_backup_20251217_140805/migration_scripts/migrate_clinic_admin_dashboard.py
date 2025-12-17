"""
Migration script to add staff_shifts table for clinic admin dashboard
This table stores shift timings for doctors and receptionists at specific clinics
"""

import sqlite3
from datetime import datetime

def migrate():
    print("Starting migration: Add staff_shifts table")
    
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()
    
    try:
        # Check if staff_shifts table already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='staff_shifts'")
        if cursor.fetchone():
            print("✓ staff_shifts table already exists")
        else:
            # Create staff_shifts table
            cursor.execute('''
                CREATE TABLE staff_shifts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    clinic_id INTEGER NOT NULL,
                    day_of_week TEXT CHECK(day_of_week IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')) NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE
                )
            ''')
            print("✓ Created staff_shifts table")
        
        # Create indexes for better performance
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_staff_shifts_user'")
        if not cursor.fetchone():
            cursor.execute('CREATE INDEX idx_staff_shifts_user ON staff_shifts(user_id)')
            print("✓ Created index on user_id")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_staff_shifts_clinic'")
        if not cursor.fetchone():
            cursor.execute('CREATE INDEX idx_staff_shifts_clinic ON staff_shifts(clinic_id)')
            print("✓ Created index on clinic_id")
        
        # Check if clinic_staff_association table exists (for many-to-many relationship)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clinic_staff_association'")
        if cursor.fetchone():
            print("✓ clinic_staff_association table already exists")
        else:
            # Create clinic_staff_association table for many-to-many relationship
            cursor.execute('''
                CREATE TABLE clinic_staff_association (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    clinic_id INTEGER NOT NULL,
                    role TEXT CHECK(role IN ('doctor', 'reception')) NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE,
                    UNIQUE(user_id, clinic_id, role)
                )
            ''')
            print("✓ Created clinic_staff_association table")
        
        # Create index for clinic_staff_association
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_clinic_staff_user'")
        if not cursor.fetchone():
            cursor.execute('CREATE INDEX idx_clinic_staff_user ON clinic_staff_association(user_id)')
            print("✓ Created index on clinic_staff_association.user_id")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_clinic_staff_clinic'")
        if not cursor.fetchone():
            cursor.execute('CREATE INDEX idx_clinic_staff_clinic ON clinic_staff_association(clinic_id)')
            print("✓ Created index on clinic_staff_association.clinic_id")
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {str(e)}")
        raise
    
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
