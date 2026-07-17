import os
import sqlite3
import psycopg2

def migrate():
    print("=== Local SQLite to Supabase Migration Tool ===")
    print("This will copy your local users and synchronized reports to your live Supabase cloud database.")
    
    supabase_url = input("\nEnter your Supabase connection string (URI): ").strip()
    if not supabase_url:
        print("Error: No connection string provided.")
        return
        
    sqlite_db = "database.db"
    if not os.path.exists(sqlite_db):
        print(f"Error: Local database file '{sqlite_db}' not found.")
        return
        
    print(f"\n1. Connecting to local SQLite database '{sqlite_db}'...")
    sqlite_conn = sqlite3.connect(sqlite_db)
    sqlite_cursor = sqlite_conn.cursor()
    
    print("2. Connecting to Supabase PostgreSQL...")
    try:
        if supabase_url.startswith("postgres://"):
            supabase_url = supabase_url.replace("postgres://", "postgresql://", 1)
        pg_conn = psycopg2.connect(supabase_url)
        pg_cursor = pg_conn.cursor()
    except Exception as e:
        print(f"Connection failed: {e}")
        sqlite_conn.close()
        return

    try:
        print("3. Ensuring tables exist in Supabase...")
        pg_cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                phone TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
            )
        """)
        pg_cursor.execute("""
            CREATE TABLE IF NOT EXISTS financial_entries (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                particulars TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                report_date TEXT DEFAULT '',
                unit TEXT DEFAULT ''
            )
        """)
        pg_conn.commit()

        # Migrate Users
        print("4. Migrating registered users...")
        sqlite_cursor.execute("SELECT phone, password_hash, role FROM users")
        users = sqlite_cursor.fetchall()
        
        user_count = 0
        for u in users:
            phone, pwd_hash, role = u
            pg_cursor.execute("SELECT 1 FROM users WHERE phone = %s", (phone,))
            if not pg_cursor.fetchone():
                pg_cursor.execute("INSERT INTO users (phone, password_hash, role) VALUES (%s, %s, %s)", (phone, pwd_hash, role))
                user_count += 1
        pg_conn.commit()
        print(f"   -> Migrated {user_count} new users.")

        # Migrate Financial Entries
        print("5. Migrating reports and entry data...")
        sqlite_cursor.execute("SELECT username, particulars, category, amount, report_date, unit FROM financial_entries")
        entries = sqlite_cursor.fetchall()
        
        entry_count = 0
        for entry in entries:
            username, particulars, category, amount, report_date, unit = entry
            pg_cursor.execute("""
                SELECT 1 FROM financial_entries 
                WHERE username = %s AND particulars = %s AND report_date = %s
            """, (username, particulars, report_date))
            if not pg_cursor.fetchone():
                pg_cursor.execute("""
                    INSERT INTO financial_entries (username, particulars, category, amount, report_date, unit) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (username, particulars, category, amount, report_date, unit))
                entry_count += 1
        pg_conn.commit()
        print(f"   -> Migrated {entry_count} database entries.")
        
        print("\n=== Migration completed successfully! ===")
        
    except Exception as e:
        print(f"\nError during migration: {e}")
        pg_conn.rollback()
    finally:
        sqlite_conn.close()
        pg_conn.close()

if __name__ == "__main__":
    migrate()
