CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    qr_code TEXT UNIQUE,
    ref_length_mm REAL,
    ref_width_mm REAL,
    ref_height_mm REAL,
    notes TEXT
);


CREATE TABLE IF NOT EXISTS measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER REFERENCES products(id),
    user_id INTEGER REFERENCES users(id),
    length_mm REAL,
    width_mm REAL,
    height_mm REAL,
    delta_pct REAL,
    verified_ok INTEGER,
    measured_at DATETIME DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS packing_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT
);


CREATE TABLE IF NOT EXISTS packing_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES packing_sessions(id),
    measurement_id INTEGER REFERENCES measurements(id),
    quantity INTEGER
);


CREATE TABLE IF NOT EXISTS packing_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES packing_sessions(id),
    variant_index INTEGER,
    box_l_mm REAL,
    box_h_mm REAL,
    box_w_mm REAL,
    box_volume_cm3 REAL,
    placements_json TEXT,
    selected INTEGER
);