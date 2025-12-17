import sqlite3
from werkzeug.security import generate_password_hash

def auto_create_admins():
    print("--- Checking Clinic Admins ---")
    conn = sqlite3.connect('clinic.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Get all clinics
    clinics = cursor.execute("SELECT id, name FROM clinics").fetchall()
    print(f"Found {len(clinics)} Clinics:")
    
    new_admins = []
    
    for clinic in clinics:
        c_id = clinic['id']
        c_name = clinic['name']
        
        # Check if already has admin
        existing = cursor.execute("SELECT username FROM users WHERE role='clinic_admin' AND clinic_id=?", (c_id,)).fetchone()
        
        if existing:
            print(f"  [✓] {c_name}: Has admin '{existing['username']}'")
        else:
            # Create new admin
            safe_name = c_name.lower().replace(' ', '_').replace('.', '')
            username = f"admin_{safe_name}"
            # Ensure unique in case of name collision
            if cursor.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone():
                username = f"admin_{safe_name}_{c_id}"
                
            full_name = f"Admin {c_name}"
            email = f"admin_{c_id}@clinic.com"
            password = generate_password_hash('admin123')
            
            try:
                cursor.execute(
                    "INSERT INTO users (username, full_name, email, phone, password, role, clinic_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (username, full_name, email, "9999999999", password, 'clinic_admin', c_id)
                )
                print(f"  [+] {c_name}: Created admin '{username}' (Pass: admin123)")
                new_admins.append((c_name, username))
            except Exception as e:
                print(f"  [!] {c_name}: Failed to create admin: {e}")

    conn.commit()
    conn.close()
    
    if new_admins:
        print("\nSUMMARY OF NEW ADMINS:")
        print("| Clinic | Username | Password |")
        print("|---|---|---|")
        for c, u in new_admins:
            print(f"| {c} | {u} | admin123 |")
    else:
        print("\nAll clinics already have admins.")

if __name__ == "__main__":
    auto_create_admins()
