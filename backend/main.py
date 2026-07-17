import os
import hashlib
import sqlite3
import io
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd

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

# --- DATABASE SETUP ---
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            phone TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)
    # Submissions storage table
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
    
    # Create default users if empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        pwd_hash = hashlib.sha256("admin123".encode()).hexdigest()
        # Seed test users and master admin
        cursor.execute("INSERT INTO users VALUES ('9876543210', ?, 'User Dashboard')", (pwd_hash,))
        cursor.execute("INSERT INTO users VALUES ('8888888888', ?, 'User Dashboard')", (pwd_hash,))
        cursor.execute("INSERT INTO users VALUES ('9999999999', ?, 'Master Executive Dashboard')", (pwd_hash,))
    conn.commit()
    conn.close()

init_db()

# --- SCHEMAS ---
class LoginRequest(BaseModel):
    phone: str
    password: str

class FinancialEntry(BaseModel):
    particulars: str
    category: str
    amount: float

class SyncPayload(BaseModel):
    username: str
    entries: List[FinancialEntry]

# --- ENDPOINTS ---

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
    """
    Directly targets the non-uniform structure of Sheet1 in 'sample report.xlsx'
    """
    try:
        contents = await file.read()
        xls = pd.ExcelFile(io.BytesIO(contents))
        df = pd.read_excel(xls, sheet_name=0)
        
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
                    
            parsed_entries.append({
                "particulars": particular,
                "category": "Operational" if "Sales" in particular or "Expense" in particular else "General",
                "amount": amount_val
            })
            
        return {"status": "success", "entries": parsed_entries}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse target Excel sheet structure: {str(e)}")


@app.post("/api/user/sync")
def sync_user_data(payload: SyncPayload):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Clean previous submission records
        cursor.execute("DELETE FROM financial_entries WHERE username = ?", (payload.username,))
        # Insert current structured records
        for entry in payload.entries:
            cursor.execute(
                "INSERT INTO financial_entries (username, particulars, category, amount) VALUES (?, ?, ?, ?)",
                (payload.username, entry.particulars, entry.category, entry.amount)
            )
        conn.commit()
        return {"status": "success", "message": "Branch data successfully synchronized!"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/api/master/summary")
def get_master_summary():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Query all synchronized entries
    cursor.execute("SELECT username, particulars, category, amount FROM financial_entries")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return {"entries": [], "totals": {"volume": 0, "sales": 0, "expenses": 0}}
        
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
        "totals": totals
    }