import sqlite3
from contextlib import contextmanager
from typing import Iterator

from api.config import DB_PATH
from api.seed_data import DEMO_LOADS


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS loads (
    load_id TEXT PRIMARY KEY,
    origin TEXT,
    destination TEXT,
    pickup_datetime TEXT,
    delivery_datetime TEXT,
    equipment_type TEXT,
    loadboard_rate INTEGER,
    notes TEXT,
    weight INTEGER,
    commodity_type TEXT,
    num_of_pieces INTEGER,
    miles INTEGER,
    dimensions TEXT
);

CREATE TABLE IF NOT EXISTS call_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mc_number TEXT,
    carrier_name TEXT,
    dot_number INTEGER,
    load_id TEXT,
    final_rate INTEGER,
    outcome TEXT,
    sentiment TEXT,
    summary TEXT,
    transcript TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (load_id) REFERENCES loads(load_id)
);

CREATE TABLE IF NOT EXISTS reporting_calls (
    session_id TEXT PRIMARY KEY,
    mc_number TEXT,
    carrier_name TEXT,
    load_id TEXT,
    origin TEXT,
    destination TEXT,
    equipment_type TEXT,
    offered_rate INTEGER,
    carrier_requested_rate INTEGER,
    final_rate INTEGER,
    outcome TEXT NOT NULL,
    summary TEXT,
    mood TEXT,
    letterboard_rate INTEGER,
    last_offered_rate INTEGER,
    call_duration_seconds INTEGER,
    negotiation_rounds INTEGER,
    tool_call_count INTEGER,
    call_status TEXT,
    call_end_event TEXT,
    transfer_completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS booking_intakes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_reference TEXT UNIQUE,
    mc_number TEXT NOT NULL,
    carrier_name TEXT,
    dot_number INTEGER,
    load_id TEXT NOT NULL,
    agreed_rate INTEGER NOT NULL,
    negotiation_rounds INTEGER,
    outcome TEXT DEFAULT 'queued_for_sales_rep',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (load_id) REFERENCES loads(load_id)
);

CREATE TABLE IF NOT EXISTS negotiation_sessions (
    session_id TEXT NOT NULL,
    load_id TEXT NOT NULL,

    carrier_mc TEXT,

    status TEXT NOT NULL DEFAULT 'active',
    round_count INTEGER NOT NULL DEFAULT 0,

    last_carrier_offer INTEGER,
    last_nancy_offer INTEGER,
    final_rate INTEGER,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (session_id, load_id),

    CHECK (status IN ('active', 'accepted', 'rejected', 'transferred', 'expired')),
    CHECK (round_count >= 0 AND round_count <= 3)
);

CREATE TABLE IF NOT EXISTS negotiation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    session_id TEXT NOT NULL,
    load_id TEXT NOT NULL,

    actor TEXT NOT NULL,
    event_type TEXT NOT NULL,
    amount INTEGER,
    round_number INTEGER,

    metadata TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (session_id, load_id)
        REFERENCES negotiation_sessions (session_id, load_id)
        ON DELETE CASCADE,

    CHECK (actor IN ('carrier', 'nancy', 'paul', 'system')),
    CHECK (
        event_type IN (
            'opening_offer',
            'carrier_offer',
            'nancy_counter',
            'accepted',
            'rejected',
            'transfer',
            'error'
        )
    ),
    CHECK (round_number IS NULL OR (round_number >= 0 AND round_number <= 3))
);
"""


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_connection() -> Iterator[sqlite3.Connection]:
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with db_connection() as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()


def seed_demo_loads() -> int:
    with db_connection() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO loads (
                load_id,
                origin,
                destination,
                pickup_datetime,
                delivery_datetime,
                equipment_type,
                loadboard_rate,
                notes,
                weight,
                commodity_type,
                num_of_pieces,
                miles,
                dimensions
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            DEMO_LOADS,
        )
        conn.commit()

    return len(DEMO_LOADS)
