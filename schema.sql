-- 1. Create Venues Table
CREATE TABLE IF NOT EXISTS venues (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    capacity INT NOT NULL,
    category VARCHAR(50) NOT NULL
);

-- 2. Create Events Table
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    event_date DATE NOT NULL,
    description TEXT,
    image_url TEXT
);

-- 3. Create Bookings Table
CREATE TABLE IF NOT EXISTS bookings (
    id SERIAL PRIMARY KEY,
    member_id VARCHAR(50) NOT NULL,
    venue_id INT REFERENCES venues(id),
    booking_date DATE NOT NULL,
    purpose VARCHAR(255),
    status VARCHAR(20) DEFAULT 'Confirmed'
);

-- ==========================================
-- POPULATE SAMPLE DATA
-- ==========================================

-- Insert Venues
INSERT INTO venues (name, capacity, category) VALUES
('Grand Banquet Hall', 350, 'Hall'),
('Main Club Lawns', 800, 'Lawn'),
('VIP Cottage 1', 4, 'Cottage'),
('VIP Cottage 2', 4, 'Cottage'),
('Executive Suite A', 2, 'Room')
ON CONFLICT DO NOTHING;

-- Insert Upcoming Club Events
INSERT INTO events (title, event_date, description, image_url) VALUES
('Annual Executive Dinner', '2026-09-15', 'An evening of live jazz music, grand buffet dining, and committee addresses.', 'https://images.unsplash.com/photo-1511795409834-ef04bbd61622?w=600'),
('Diwali Festive Gala', '2026-10-24', 'Family fireworks display, festive food stalls, and club illumination.', 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=600'),
('New Year Gala Night', '2026-12-31', 'Celebratory ball with DJ entertainment and dinner on the Main Lawns.', 'https://images.unsplash.com/photo-1464366400600-7168b8af9bc3?w=600')
ON CONFLICT DO NOTHING;

-- Insert Sample Bookings (dates around September 2026)
INSERT INTO bookings (member_id, venue_id, booking_date, purpose, status) VALUES
('SC-1002', 1, '2026-09-02', 'Family Wedding Reception', 'Confirmed'),
('SC-1045', 1, '2026-09-03', 'Corporate AGM', 'Confirmed'),
('SC-0891', 2, '2026-09-02', 'Anniversary Celebration', 'Confirmed'),
('SC-0542', 3, '2026-09-01', 'Guest Stay', 'Confirmed'),
('SC-0542', 3, '2026-09-02', 'Guest Stay', 'Confirmed'),
('SC-1109', 4, '2026-09-03', 'Personal Stay', 'Confirmed')
ON CONFLICT DO NOTHING;