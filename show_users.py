import sqlite3
import hashlib

def show_users():
    db_path = "database.db"
    print("=== Registered Users Viewer ===")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if users table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            print("Error: The 'users' table does not exist in the database.")
            conn.close()
            return
            
        cursor.execute("SELECT phone, password_hash, role FROM users")
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            print("No users registered in the local database.")
            return
            
        print(f"\nFound {len(rows)} registered users:\n")
        print(f"{'Phone Number':<15} | {'Role':<30} | {'Password (Plain/Hash Status)':<35}")
        print("-" * 88)
        
        # Standard hash for admin123
        admin123_hash = hashlib.sha256("admin123".encode()).hexdigest()
        
        for phone, pwd_hash, role in rows:
            pwd_status = ""
            if len(pwd_hash) == 64:
                # Password is a SHA-256 hash
                if pwd_hash == admin123_hash:
                    pwd_status = "admin123 (hashed)"
                else:
                    pwd_status = f"Hashed: {pwd_hash[:10]}..."
            else:
                # Password is in plain-text
                pwd_status = f"{pwd_hash} (plain-text)"
                
            print(f"{phone:<15} | {role:<30} | {pwd_status:<35}")
            
        print("\n===============================")
        
    except Exception as e:
        print(f"Error accessing database: {e}")

if __name__ == "__main__":
    show_users()
