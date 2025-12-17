
import sqlite3

def inspect_receptionists():
    conn = sqlite3.connect('clinic.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("--- Users with role 'reception' ---")
    users = cursor.execute("SELECT id, username, full_name, role FROM users WHERE role='reception'").fetchall()
    if not users:
        print("No users with role 'reception' found.")
    else:
        for u in users:
            print(dict(u))

    print("\n--- Clinic Staff Association (role='reception') ---")
    associations = cursor.execute("SELECT * FROM clinic_staff_association WHERE role='reception'").fetchall()
    if not associations:
        print("No receptionist associations found in clinic_staff_association.")
    else:
        for a in associations:
            print(dict(a))

    conn.close()

if __name__ == "__main__":
    inspect_receptionists()
