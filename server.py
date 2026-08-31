import os
import hashlib
from datetime import date
from contextlib import asynccontextmanager
import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db():
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.strip().encode("utf-8")).hexdigest()

@asynccontextmanager
async def lifespan(app: FastAPI):
    if DATABASE_URL:
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            id SERIAL PRIMARY KEY,
                            username VARCHAR(50) UNIQUE NOT NULL,
                            password_hash VARCHAR(255) NOT NULL,
                            full_name VARCHAR(100) NOT NULL,
                            role VARCHAR(20) DEFAULT 'member',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        CREATE TABLE IF NOT EXISTS events (
                            id SERIAL PRIMARY KEY,
                            title VARCHAR(150) NOT NULL,
                            event_date DATE NOT NULL,
                            description TEXT,
                            poster_url TEXT,
                            drive_link TEXT,
                            gallery_urls TEXT[] DEFAULT '{}',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        CREATE TABLE IF NOT EXISTS venues (
                            id SERIAL PRIMARY KEY,
                            name VARCHAR(100) UNIQUE NOT NULL,
                            category VARCHAR(50) NOT NULL,
                            capacity INT NOT NULL
                        );
                        CREATE TABLE IF NOT EXISTS bookings (
                            id SERIAL PRIMARY KEY,
                            booker_name VARCHAR(100),
                            member_id VARCHAR(50),
                            venue_id INT REFERENCES venues(id) ON DELETE CASCADE,
                            booking_date DATE NOT NULL,
                            purpose VARCHAR(255),
                            status VARCHAR(20) DEFAULT 'Confirmed',
                            created_by VARCHAR(50) DEFAULT 'Self',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        CREATE TABLE IF NOT EXISTS flash_notices (
                            id SERIAL PRIMARY KEY,
                            title VARCHAR(150) NOT NULL,
                            message TEXT NOT NULL,
                            image_url TEXT,
                            start_date DATE NOT NULL,
                            end_date DATE NOT NULL,
                            is_active BOOLEAN DEFAULT TRUE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    
                    cur.execute("SELECT COUNT(*) AS cnt FROM venues;")
                    if cur.fetchone()["cnt"] == 0:
                        cur.execute("""
                            INSERT INTO venues (name, category, capacity) VALUES
                            ('Grand Banquet Hall', 'Banquet & Celebrations', 350),
                            ('Executive Lounge & Bar', 'Lounge & Dining', 80),
                            ('Poolside Green Lawn', 'Open Air Lawns', 500),
                            ('Deluxe Guest Suite 101', 'Guest Accommodation', 4),
                            ('Presidential Cottage 102', 'Guest Accommodation', 6);
                        """)

                    admin_hash = hash_password("admin123")
                    member_hash = hash_password("member123")
                    
                    cur.execute("""
                        INSERT INTO users (username, password_hash, full_name, role)
                        VALUES 
                        ('admin', %s, 'Club Administrator', 'admin'),
                        ('SC-1001', %s, 'Ashish Agrawal', 'member')
                        ON CONFLICT (username) DO UPDATE 
                        SET password_hash = EXCLUDED.password_hash;
                    """, (admin_hash, member_hash))
                    
                    conn.commit()
        except Exception as e:
            print(f"Startup DB init notice: {e}")
    yield

app = FastAPI(title="Steel Club Enterprise Portal", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Models
class LoginReq(BaseModel):
    username: str
    password: str

class PasswordChangeReq(BaseModel):
    username: str
    current_password: str
    new_password: str

class MemberUpsertReq(BaseModel):
    username: str
    full_name: str
    password: str
    role: Optional[str] = "member"

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
    id: Optional[int] = None
    title: str
    message: str
    image_url: Optional[str] = ""
    start_date: str
    end_date: str
    is_active: Optional[bool] = True

# 1. AUTHENTICATION & MEMBERS
@app.post("/api/login")
def login(req: LoginReq):
    hashed = hash_password(req.password)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, full_name, role FROM users WHERE LOWER(username) = LOWER(%s) AND password_hash = %s;",
                (req.username.strip(), hashed)
            )
            user = cur.fetchone()
            if not user:
                raise HTTPException(status_code=401, detail="Invalid username or password")
            return user

@app.post("/api/change-password")
def change_password(req: PasswordChangeReq):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM users WHERE LOWER(username) = LOWER(%s) AND password_hash = %s;",
                (req.username.strip(), hash_password(req.current_password))
            )
            if not cur.fetchone():
                raise HTTPException(status_code=400, detail="Current password incorrect")
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE LOWER(username) = LOWER(%s);",
                (hash_password(req.new_password), req.username.strip())
            )
            conn.commit()
            return {"status": "Password changed successfully"}

@app.get("/api/admin/members")
def get_all_members():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, username, full_name, role, created_at::text FROM users ORDER BY id ASC;")
                return cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/members")
def admin_upsert_member(req: MemberUpsertReq):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (username, password_hash, full_name, role)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (username) DO UPDATE 
                    SET password_hash = EXCLUDED.password_hash, full_name = EXCLUDED.full_name, role = EXCLUDED.role;
                    """,
                    (req.username.strip(), hash_password(req.password), req.full_name.strip(), req.role)
                )
                conn.commit()
                return {"status": "Member updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/admin/members/{user_id}")
def delete_member(user_id: int):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE id = %s AND username != 'admin';", (user_id,))
                conn.commit()
                return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 2. FLASH NOTICES
@app.get("/api/active-flash-notice")
def get_active_flash_notice():
    today = date.today().isoformat()
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, title, message, image_url, start_date::text, end_date::text 
                    FROM flash_notices 
                    WHERE is_active = TRUE AND start_date <= %s AND end_date >= %s 
                    ORDER BY id DESC LIMIT 1;
                    """,
                    (today, today)
                )
                return cur.fetchone()
    except Exception:
        return None

@app.get("/api/admin/flash-notices")
def get_all_flash_notices():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, title, message, image_url, start_date::text, end_date::text, is_active FROM flash_notices ORDER BY id DESC;")
                return cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/flash-notice")
def save_flash_notice(req: FlashNoticeReq):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                if req.id:
                    cur.execute(
                        """
                        UPDATE flash_notices 
                        SET title=%s, message=%s, image_url=%s, start_date=%s, end_date=%s, is_active=%s
                        WHERE id=%s;
                        """,
                        (req.title, req.message, req.image_url, req.start_date, req.end_date, req.is_active, req.id)
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO flash_notices (title, message, image_url, start_date, end_date, is_active)
                        VALUES (%s, %s, %s, %s, %s, %s);
                        """,
                        (req.title, req.message, req.image_url, req.start_date, req.end_date, req.is_active)
                    )
                conn.commit()
                return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/admin/flash-notices/{notice_id}")
def delete_flash_notice(notice_id: int):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM flash_notices WHERE id = %s;", (notice_id,))
                conn.commit()
                return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 3. EVENTS
@app.get("/api/events")
def get_events():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, title, event_date::text, description, poster_url, drive_link, gallery_urls FROM events ORDER BY event_date ASC;")
                events = cur.fetchall()
                for ev in events:
                    if ev.get("gallery_urls") is None:
                        ev["gallery_urls"] = []
                return events
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/events")
def upsert_event(req: EventUpsertReq):
    try:
        gallery_list = [u.strip() for u in req.gallery_urls if u.strip()] if req.gallery_urls else []
        with get_db() as conn:
            with conn.cursor() as cur:
                if req.id:
                    cur.execute(
                        """
                        UPDATE events 
                        SET title=%s, event_date=%s, description=%s, poster_url=%s, drive_link=%s, gallery_urls=%s
                        WHERE id=%s;
                        """,
                        (req.title, req.event_date, req.description, req.poster_url, req.drive_link, gallery_list, req.id)
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO events (title, event_date, description, poster_url, drive_link, gallery_urls)
                        VALUES (%s, %s, %s, %s, %s, %s);
                        """,
                        (req.title, req.event_date, req.description, req.poster_url, req.drive_link, gallery_list)
                    )
                conn.commit()
                return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/admin/events/{event_id}")
def delete_event(event_id: int):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM events WHERE id = %s;", (event_id,))
                conn.commit()
                return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 4. VENUES & BOOKINGS
@app.get("/api/venues-availability")
def get_availability():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, category, capacity FROM venues ORDER BY id ASC;")
                venues = cur.fetchall()
                cur.execute(
                    """
                    SELECT b.id, COALESCE(b.booker_name, b.member_id) AS booker_name, b.member_id, 
                           b.venue_id, b.booking_date::text, b.purpose, b.status, v.name as venue_name 
                    FROM bookings b 
                    JOIN venues v ON b.venue_id = v.id 
                    ORDER BY b.booking_date DESC;
                    """
                )
                bookings = cur.fetchall()
                return {"venues": venues, "bookings": bookings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/book-venue")
def create_booking(req: BookingCreateReq):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM venues WHERE name = %s;", (req.venue_name,))
                venue = cur.fetchone()
                if not venue:
                    raise HTTPException(status_code=404, detail="Venue not found")
                
                cur.execute(
                    "SELECT id FROM bookings WHERE venue_id = %s AND booking_date = %s;",
                    (venue["id"], req.booking_date)
                )
                if cur.fetchone():
                    raise HTTPException(status_code=400, detail="This venue is already booked for the selected date.")
                
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/admin/bookings/{booking_id}")
def delete_booking(booking_id: int):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM bookings WHERE id = %s;", (booking_id,))
                conn.commit()
                return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 5. FRONTEND
@app.get("/", response_class=HTMLResponse)
def read_root():
    path = os.path.join("static", "index.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Error: static/index.html not found</h1>"