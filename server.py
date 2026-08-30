import os
import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Steel Club Durgapur API")

# Enable CORS for cross-origin requests
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
    # Clean connection using modern psycopg v3
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

class BookingRequest(BaseModel):
    member_id: str
    venue_name: str
    booking_date: str
    purpose: str

# Serve uploaded static media/images if directory exists
if os.path.exists("static/images"):
    app.mount("/images", StaticFiles(directory="static/images"), name="images")

# 1. API Route: Fetch all events
@app.get("/api/events")
def get_events():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM events ORDER BY event_date ASC;")
                events = cur.fetchall()
                return events
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 2. API Route: Fetch venues & availability status
@app.get("/api/venues-availability")
def get_availability():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, category, capacity FROM venues ORDER BY id ASC;")
                venues = cur.fetchall()
                cur.execute("SELECT venue_id, booking_date, status FROM bookings;")
                bookings = cur.fetchall()
                return {"venues": venues, "bookings": bookings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 3. API Route: Submit new booking
@app.post("/api/book-venue")
def create_booking(booking: BookingRequest):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM venues WHERE name = %s;", (booking.venue_name,))
                venue = cur.fetchone()
                if not venue:
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
                return {"status": "success", "booking_id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 4. Frontend Route: Direct HTML rendering
@app.get("/", response_class=HTMLResponse)
def read_root():
    html_file_path = os.path.join("static", "index.html")
    if os.path.exists(html_file_path):
        with open(html_file_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Error: static/index.html not found</h1>"