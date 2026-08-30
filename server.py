import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Steel Club Durgapur API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    return psycopg2.connect(DATABASE_URL, sslmode="require")

class BookingRequest(BaseModel):
    member_id: str
    venue_name: str
    booking_date: str
    purpose: str

@app.get("/api/events")
def get_events():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM events ORDER BY event_date ASC;")
        events = cur.fetchall()
        cur.close()
        conn.close()
        return events
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/venues-availability")
def get_availability():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, name, category FROM venues ORDER BY id ASC;")
        venues = cur.fetchall()
        cur.execute("SELECT venue_id, booking_date, status FROM bookings;")
        bookings = cur.fetchall()
        cur.close()
        conn.close()
        return {"venues": venues, "bookings": bookings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/book-venue")
def create_booking(booking: BookingRequest):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id FROM venues WHERE name = %s;", (booking.venue_name,))
        venue = cur.fetchone()
        if not venue:
            cur.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Venue not found")
            
        cur.execute(
            """
            INSERT INTO bookings (member_id, venue_id, booking_date, purpose, status)
            VALUES (%s, %s, %s, %s, 'Confirmed') RETURNING id;
            """,
            (booking.member_id, venue["id"], booking.booking_date, booking.purpose)
        )
        new_id = cur.fetchone()["id"]
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "success", "booking_id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# DIRECT HTML RENDER (Forces browser to render real design)
@app.get("/", response_class=HTMLResponse)
def read_root():
    html_file_path = os.path.join("static", "index.html")
    if os.path.exists(html_file_path):
        with open(html_file_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Error: static/index.html not found</h1>"