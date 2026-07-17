import os
import hashlib
import sqlite3
import io
import webbrowser
import re
from datetime import datetime, date
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import uvicorn

app = FastAPI(title="Corporate Financial Aggregation API", version="1.0.0")

# Enable CORS for frontend flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "database.db"

# --- HELPER FUNCTIONS ---
def extract_date_from_df(df) -> str:
    # Scan cells in first 15 rows and columns for any date pattern
    # Match dd/mm/yyyy, dd-mm-yyyy, yyyy-mm-dd
    date_pattern = re.compile(r'(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})|(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})')
    for col in df.columns:
        # Check first 15 rows of this column
        for val in df[col].head(15):
            if pd.notna(val):
                if isinstance(val, (pd.Timestamp, date)):
                    return val.strftime("%Y-%m-%d")
                val_str = str(val).strip()
                if "date" in val_str.lower():
                    match = date_pattern.search(val_str)
                    if match:
                        try:
                            # Clean word prefix
                            cleaned = re.sub(r'(?i)date\s*[:\-]?\s*', '', val_str).strip()
                            parsed_dt = pd.to_datetime(cleaned, dayfirst=True)
                            return parsed_dt.strftime("%Y-%m-%d")
                        except:
                            pass
                match = date_pattern.search(val_str)
                if match and len(val_str) < 30:
                    try:
                        parsed_dt = pd.to_datetime(match.group(0), dayfirst=True)
                        return parsed_dt.strftime("%Y-%m-%d")
                    except:
                        pass
    return date.today().strftime("%Y-%m-%d")

# --- DATABASE SETUP ---
DATABASE_URL = os.environ.get("DATABASE_URL")

class PostgresRowWrapper:
    def __init__(self, data_dict):
        self.data = data_dict
        
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.data.values())[key]
        return self.data[key]
        
    def keys(self):
        return self.data.keys()
        
    def values(self):
        return self.data.values()
        
    def items(self):
        return self.data.items()
        
    def get(self, key, default=None):
        return self.data.get(key, default)
        
    def __len__(self):
        return len(self.data)
        
    def __iter__(self):
        return iter(self.data)
        
    def __repr__(self):
        return repr(self.data)

class PostgresCursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor
        
    def execute(self, query, params=None):
        if params is None:
            params = ()
        # Convert SQLite ? placeholders to PostgreSQL %s placeholders
        query = query.replace('?', '%s')
        self.cursor.execute(query, params)
        
    def fetchone(self):
        row = self.cursor.fetchone()
        if row is not None:
            return PostgresRowWrapper(row)
        return None
        
    def fetchall(self):
        rows = self.cursor.fetchall()
        return [PostgresRowWrapper(r) for r in rows]
        
    def __getattr__(self, name):
        return getattr(self.cursor, name)

class PostgresConnectionWrapper:
    def __init__(self, conn):
        self.conn = conn
        
    def cursor(self):
        from psycopg2.extras import RealDictCursor
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        return PostgresCursorWrapper(cursor)
        
    def commit(self):
        self.conn.commit()
        
    def rollback(self):
        self.conn.rollback()
        
    def close(self):
        self.conn.close()

def get_db_connection():
    if DATABASE_URL:
        import psycopg2
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(url)
        return PostgresConnectionWrapper(conn)
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if DATABASE_URL:
        # PostgreSQL initialization
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                phone TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
            )
        """)
        cursor.execute("""
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
    else:
        # SQLite initialization
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                phone TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS financial_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                particulars TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Schema Migration: Add report_date if not present
        cursor.execute("PRAGMA table_info(financial_entries)")
        columns = [row[1] for row in cursor.fetchall()]
        if "report_date" not in columns:
            cursor.execute("ALTER TABLE financial_entries ADD COLUMN report_date TEXT DEFAULT ''")
            
        # Auto-migrate any existing empty dates to today's date
        cursor.execute("UPDATE financial_entries SET report_date = ? WHERE report_date = '' OR report_date IS NULL", 
                       (date.today().strftime("%Y-%m-%d"),))
                       
        # Schema Migration: Add unit if not present
        if "unit" not in columns:
            cursor.execute("ALTER TABLE financial_entries ADD COLUMN unit TEXT DEFAULT ''")
            
    # Create default users if empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        pwd_hash = hashlib.sha256("admin123".encode()).hexdigest()
        # Seed test users and master admin
        cursor.execute("INSERT INTO users (phone, password_hash, role) VALUES ('9876543210', ?, 'User Dashboard')", (pwd_hash,))
        cursor.execute("INSERT INTO users (phone, password_hash, role) VALUES ('8888888888', ?, 'User Dashboard')", (pwd_hash,))
        cursor.execute("INSERT INTO users (phone, password_hash, role) VALUES ('9999999999', ?, 'Master Executive Dashboard')", (pwd_hash,))
    conn.commit()
    conn.close()

init_db()

# --- SCHEMAS ---
class LoginRequest(BaseModel):
    phone: str
    password: str

class RegisterRequest(BaseModel):
    phone: str
    password: str
    role: str

class FinancialEntry(BaseModel):
    particulars: str
    category: str
    unit: Optional[str] = ""
    amount: float

class SyncPayload(BaseModel):
    username: str
    date: str
    entries: List[FinancialEntry]

# --- ENDPOINTS ---

@app.post("/api/auth/register")
def register(data: RegisterRequest):
    if data.role == "Master Executive Dashboard":
        raise HTTPException(status_code=403, detail="Creation of Master Executive accounts is restricted.")
    if data.role not in ["User Dashboard"]:
        raise HTTPException(status_code=400, detail="Invalid role type.")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if user already exists
    cursor.execute("SELECT 1 FROM users WHERE phone = ?", (data.phone,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Phone number is already registered.")
    
    # Hash password and insert
    pwd_hash = hashlib.sha256(data.password.encode()).hexdigest()
    try:
        cursor.execute("INSERT INTO users (phone, password_hash, role) VALUES (?, ?, ?)", 
                       (data.phone, pwd_hash, data.role))
        conn.commit()
        return {"status": "success", "message": "User registered successfully!"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/api/auth/login")
def login(data: LoginRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    pwd_hash = hashlib.sha256(data.password.encode()).hexdigest()
    cursor.execute("SELECT role FROM users WHERE phone = ? AND password_hash = ?", (data.phone, pwd_hash))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid phone number or password.")
    
    return {"status": "success", "username": f"Branch_{data.phone[-4:]}", "role": user["role"]}


@app.post("/api/user/parse-excel")
async def parse_excel(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        xls = pd.ExcelFile(io.BytesIO(contents))
        df = pd.read_excel(xls, sheet_name=0)
        
        extracted_date = extract_date_from_df(df)
        
        parsed_entries = []
        # Safely parse matching row cells
        for idx, row in df.iterrows():
            particular = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
            if not particular or particular == "Particulars" or particular == "nan":
                continue
            
            # Extract the numerical value
            amount_val = 0.0
            for col_idx in range(2, len(row)):
                cell_val = row.iloc[col_idx]
                if pd.notna(cell_val) and isinstance(cell_val, (int, float)):
                    amount_val = float(cell_val)
                    break
            
            # Determine the unit based on particulars keywords
            part_lower = particular.lower()
            if "volume" in part_lower:
                unit_val = "MT"
            elif "rate" in part_lower:
                unit_val = "Rs./MT"
            elif any(k in part_lower for k in ["sales", "expense", "balance"]):
                unit_val = "Rs."
            else:
                unit_val = ""
                    
            parsed_entries.append({
                "particulars": particular,
                "category": "Operational" if "Sales" in particular or "Expense" in particular else "General",
                "unit": unit_val,
                "amount": amount_val
            })
            
        return {"status": "success", "entries": parsed_entries, "date": extracted_date}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse target Excel sheet structure: {str(e)}")


@app.post("/api/user/sync")
def sync_user_data(payload: SyncPayload):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Clean previous submission records for same username and report_date
        cursor.execute("DELETE FROM financial_entries WHERE username = ? AND report_date = ?", 
                       (payload.username, payload.date))
        # Insert current structured records
        for entry in payload.entries:
            cursor.execute(
                "INSERT INTO financial_entries (username, particulars, category, amount, report_date, unit) VALUES (?, ?, ?, ?, ?, ?)",
                (payload.username, entry.particulars, entry.category, entry.amount, payload.date, entry.unit)
            )
        conn.commit()
        return {"status": "success", "message": "Branch data successfully synchronized!"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/api/user/report")
def get_user_report(username: str, date: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT particulars, category, amount, unit FROM financial_entries WHERE username = ? AND report_date = ?",
        (username, date)
    )
    rows = cursor.fetchall()
    conn.close()
    return {"entries": [dict(r) for r in rows]}


@app.get("/api/master/summary")
def get_master_summary(date: Optional[str] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # If date is not provided, query the latest report_date from database
    if not date:
        cursor.execute("SELECT MAX(report_date) FROM financial_entries WHERE report_date != ''")
        res = cursor.fetchone()
        date = res[0] if res and res[0] else datetime.now().strftime("%Y-%m-%d")
        
    # Query synchronized entries for specific date
    cursor.execute("SELECT username, particulars, category, amount, unit FROM financial_entries WHERE report_date = ?", (date,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return {"entries": [], "raw_entries": [], "totals": {"volume": 0, "sales": 0, "expenses": 0}, "date": date}
        
    df = pd.DataFrame([dict(r) for r in rows])
    
    # Generate dynamic calculations
    volume_df = df[df['particulars'].str.contains("Volume", case=False, na=False)]
    sales_df = df[df['particulars'].str.contains("Total Sales", case=False, na=False)]
    expense_df = df[df['particulars'].str.contains("Expenses", case=False, na=False)]
    
    totals = {
        "volume": float(volume_df['amount'].sum()) if not volume_df.empty else 0.0,
        "sales": float(sales_df['amount'].sum()) if not sales_df.empty else 0.0,
        "expenses": float(expense_df['amount'].sum()) if not expense_df.empty else 0.0,
    }
    
    # Structure Master Pivot view dynamically
    pivot = df.pivot_table(index="particulars", columns="username", values="amount", aggfunc="sum").fillna(0.0)
    pivot['Consolidated Amount (Rs.)'] = pivot.sum(axis=1)
    pivot = pivot.reset_index()
    
    return {
        "entries": pivot.to_dict(orient="records"),
        "raw_entries": [dict(r) for r in rows],
        "totals": totals,
        "date": date
    }


@app.get("/api/master/export")
def export_master_report(date: Optional[str] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if not date:
        cursor.execute("SELECT MAX(report_date) FROM financial_entries WHERE report_date != ''")
        res = cursor.fetchone()
        date = res[0] if res and res[0] else datetime.now().strftime("%Y-%m-%d")
        
    cursor.execute("SELECT username, particulars, category, amount FROM financial_entries WHERE report_date = ?", (date,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        raise HTTPException(status_code=400, detail="No synchronized records available to export for this date.")
        
    df = pd.DataFrame([dict(r) for r in rows])
    
    # Structure Master Pivot view dynamically
    pivot = df.pivot_table(index="particulars", columns="username", values="amount", aggfunc="sum").fillna(0.0)
    pivot['Consolidated Amount (Rs.)'] = pivot.sum(axis=1)
    pivot = pivot.reset_index()
    
    # Generate Excel sheet in-memory
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        pivot.to_excel(writer, sheet_name='Master Dashboard Data', index=False)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=Master_Consolidation_Report_{date}.xlsx"}
    )


# Serve frontend static files at root "/"
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


# --- BROWSER LAUNCHER & SERVER ENTRY POINT ---
if __name__ == "__main__":
    url = "http://127.0.0.1:8000"
    print(f"Opening browser to: {url}")
    webbrowser.open(url)
    
    # Start the local FastAPI server using Uvicorn
    print("Starting backend server on http://127.0.0.1:8000 ...")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
