import sqlite3

"""
Migration script to add clinic_admin role support and clinic_id association to users table.
This script updates the existing database without recreating it.
"""

def migrate():
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()
    
    print("Starting migration: Adding clinic_admin support...")
    
    try:
        # Step 1: Add clinic_id column to users table
        print("  - Adding clinic_id column to users table...")
        cursor.execute("ALTER TABLE users ADD COLUMN clinic_id INTEGER")
        print("    ✓ clinic_id column added")
        
        # Step 2: Create a new users table with updated role constraint
        print("  - Updating role constraint to include 'clinic_admin'...")
        
        # Create temporary table with new schema
        cursor.execute('''
        CREATE TABLE users_new (
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
        
        # Copy data from old table to new table
        cursor.execute('''
        INSERT INTO users_new (id, username, full_name, email, phone, password, role, specialization, clinic_id)
        SELECT id, username, full_name, email, phone, password, role, specialization, clinic_id
        FROM users
        ''')
        
        # Drop old table and rename new table
        cursor.execute("DROP TABLE users")
        cursor.execute("ALTER TABLE users_new RENAME TO users")
        print("    ✓ Role constraint updated")
        
        # Step 3: Add status column to clinics table if it doesn't exist
        print("  - Checking clinics table for status column...")
        cursor.execute("PRAGMA table_info(clinics)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'status' not in columns:
            print("  - Adding status column to clinics table...")
            cursor.execute("ALTER TABLE clinics ADD COLUMN status TEXT DEFAULT 'active'")
            print("    ✓ status column added")
        else:
            print("    ✓ status column already exists")
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        print("\nDatabase is now ready for clinic_admin users.")
        
    except sqlite3.Error as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        raise
    
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
