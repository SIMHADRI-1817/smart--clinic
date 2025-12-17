
import sqlite3
from werkzeug.security import generate_password_hash

def migrate_receptionists():
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()

    # Clinic configuration
    clinics = [
        {'id': 1, 'name': 'Downtown Clinic', 'receptionists': [
            {'name': 'Sarah Jones', 'email': 'sarah.j@downtown.com', 'user': 'sarah_downtown'},
            {'name': 'Mike Brown', 'email': 'mike.b@downtown.com', 'user': 'mike_downtown'}
        ]},
        {'id': 2, 'name': 'Uptown Clinic', 'receptionists': [
            {'name': 'Emily Davis', 'email': 'emily.d@uptown.com', 'user': 'emily_uptown'},
            {'name': 'Chris Wilson', 'email': 'chris.w@uptown.com', 'user': 'chris_uptown'}
        ]},
        {'id': 3, 'name': 'West End Clinic', 'receptionists': [
            {'name': 'Jessica Taylor', 'email': 'jessica.t@westend.com', 'user': 'jessica_westend'},
            {'name': 'David Miller', 'email': 'david.m@westend.com', 'user': 'david_westend'}
        ]}
    ]

    default_password = generate_password_hash('password123')

    print("Starting receptionist migration...")

    for clinic in clinics:
        print(f"Processing {clinic['name']} (ID: {clinic['id']})...")
        
        for recep in clinic['receptionists']:
            # Check if user exists
            cursor.execute("SELECT id FROM users WHERE username = ?", (recep['user'],))
            existing_user = cursor.fetchone()

            if existing_user:
                user_id = existing_user[0]
                print(f"  User {recep['user']} already exists (ID: {user_id}).")
            else:
                # Create user
                cursor.execute('''
                    INSERT INTO users (username, password, role, full_name, email, phone)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (recep['user'], default_password, 'reception', recep['name'], recep['email'], '555-0100'))
                user_id = cursor.lastrowid
                print(f"  Created user {recep['user']} (ID: {user_id}).")

            # Link to clinic if not already linked
            cursor.execute('''
                SELECT 1 FROM clinic_staff_association 
                WHERE user_id = ? AND clinic_id = ? AND role = 'reception'
            ''', (user_id, clinic['id']))
            
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO clinic_staff_association (user_id, clinic_id, role, is_active)
                    VALUES (?, ?, ?, 1)
                ''', (user_id, clinic['id'], 'reception'))
                print(f"  Linked {recep['user']} to {clinic['name']}.")
            else:
                print(f"  {recep['user']} already linked to {clinic['name']}.")

    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate_receptionists()
