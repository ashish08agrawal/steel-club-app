import os
import hashlib
from datetime import date
import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Steel Club Enterprise Portal")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db():
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# Models
class LoginReq(BaseModel):
    username: str
    password: str

class PasswordChangeReq(BaseModel):
    username: str
    current_password: str
    new_password: str

class BookingCreateReq(BaseModel):
    booker_name: str
    member_id: Optional[str] = "GUEST"
    venue_name: str
    booking_date: str
    purpose: str

class EventUpsertReq(BaseModel):
    id: Optional[int] = None
    title: str
    event_date: str
    description: str
    poster_url: Optional[str] = ""
    drive_link: Optional[str] = ""
    gallery_urls: Optional[List[str]] = []

class FlashNoticeReq(BaseModel):
    title: str
    message: str
    image_url: Optional[str] = ""
    start_date: str
    end_date: str

# 1. AUTHENTICATION
@app.post("/api/login")
def login(req: LoginReq):
    hashed = hash_password(req.password)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username, full_name, role FROM users WHERE username = %s AND password_hash = %s;", (req.username, hashed))
            user = cur.fetchone()
            if not user:
                raise HTTPException(status_code=401, detail="Invalid username or password")
            return user

@app.post("/api/change-password")
def change_password(req: PasswordChangeReq):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username = %s AND password_hash = %s;", (req.username, hash_password(req.current_password)))
            if not cur.fetchone():
                raise HTTPException(status_code=400, detail="Current password incorrect")
            cur.execute("UPDATE users SET password_hash = %s WHERE username = %s;", (hash_password(req.new_password), req.username))
            conn.commit()
            return {"status": "Password changed successfully"}

# 2. ACTIVE FLASH NOTICES (Scheduled)
@app.get("/api/active-flash-notice")
def get_active_flash_notice():
    today = date.today().isoformat()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM flash_notices 
                WHERE is_active = TRUE AND start_date <= %s AND end_date >= %s 
                ORDER BY id DESC LIMIT 1;
                """,
                (today, today)
            )
            return cur.fetchone()

@app.post("/api/admin/flash-notice")
def create_flash_notice(req: FlashNoticeReq):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO flash_notices (title, message, image_url, start_date, end_date)
                VALUES (%s, %s, %s, %s, %s) RETURNING id;
                """,
                (req.title, req.message, req.image_url, req.start_date, req.end_date)
            )
            conn.commit()
            return {"status": "success"}

# 3. EVENTS (Dynamic Categorization)
@app.get("/api/events")
def get_events():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM events ORDER BY event_date ASC;")
            return cur.fetchall()

@app.post("/api/admin/events")
def upsert_event(req: EventUpsertReq):
    with get_db() as conn:
        with conn.cursor() as cur:
            if req.id:
                cur.execute(
                    """
                    UPDATE events 
                    SET title=%s, event_date=%s, description=%s, poster_url=%s, drive_link=%s, gallery_urls=%s
                    WHERE id=%s;
                    """,
                    (req.title, req.event_date, req.description, req.poster_url, req.drive_link, req.gallery_urls, req.id)
                )
            else:
                cur.execute(
                    """
                    INSERT INTO events (title, event_date, description, poster_url, drive_link, gallery_urls)
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    (req.title, req.event_date, req.description, req.poster_url, req.drive_link, req.gallery_urls)
                )
            conn.commit()
            return {"status": "success"}

@app.delete("/api/admin/events/{event_id}")
def delete_event(event_id: int):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM events WHERE id = %s;", (event_id,))
            conn.commit()
            return {"status": "deleted"}

# 4. BOOKINGS (Admin All-Access + Member Booking)
@app.get("/api/venues-availability")
def get_availability():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, category, capacity FROM venues ORDER BY id ASC;")
            venues = cur.fetchall()
            cur.execute("SELECT b.*, v.name as venue_name FROM bookings b JOIN venues v ON b.venue_id = v.id ORDER BY b.booking_date DESC;")
            bookings = cur.fetchall()
            return {"venues": venues, "bookings": bookings}

@app.post("/api/book-venue")
def create_booking(req: BookingCreateReq):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM venues WHERE name = %s;", (req.venue_name,))
            venue = cur.fetchone()
            if not venue:
                raise HTTPException(status_code=404, detail="Venue not found")
            
            cur.execute(
                """
                INSERT INTO bookings (booker_name, member_id, venue_id, booking_date, purpose, status)
                VALUES (%s, %s, %s, %s, %s, 'Confirmed') RETURNING id;
                """,
                (req.booker_name, req.member_id, venue["id"], req.booking_date, req.purpose)
            )
            new_id = cur.fetchone()["id"]
            conn.commit()
            return {"status": "success", "booking_id": new_id}

@app.delete("/api/admin/bookings/{booking_id}")
def delete_booking(booking_id: int):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM bookings WHERE id = %s;", (booking_id,))
            conn.commit()
            return {"status": "deleted"}

# HTML SERVE
@app.get("/", response_class=HTMLResponse)
def read_root():
    path = os.path.join("static", "index.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Error: static/index.html not found</h1>"