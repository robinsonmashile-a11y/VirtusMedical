"""
CadenceWorks — Inbox Engine
============================
DB helpers for reading and managing the patient reply inbox.
"""

import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "virtus_health.db"


def init_inbox_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS inbox (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            from_number     TEXT,
            patient_name    TEXT,
            appointment_id  TEXT,
            body            TEXT,
            intent          TEXT,
            status          TEXT,
            auto_replied    INTEGER DEFAULT 0,
            ts              TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_all_messages(limit=200):
    """Return all inbox messages as DataFrame, newest first."""
    try:
        conn = sqlite3.connect(DB_PATH)
        df   = pd.read_sql_query("""
            SELECT id, ts, from_number, patient_name, appointment_id,
                   body, intent, status
            FROM inbox
            ORDER BY id DESC
            LIMIT ?
        """, conn, params=(limit,))
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def get_inbox_stats():
    """Summary counts for the Inbox tab header."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        total      = c.execute("SELECT COUNT(*) FROM inbox").fetchone()[0]
        confirmed  = c.execute("SELECT COUNT(*) FROM inbox WHERE intent='confirmed'").fetchone()[0]
        cancelled  = c.execute("SELECT COUNT(*) FROM inbox WHERE intent='cancelled'").fetchone()[0]
        attention  = c.execute("SELECT COUNT(*) FROM inbox WHERE status='needs_attention'").fetchone()[0]
        conn.close()
        return {
            "total":     total,
            "confirmed": confirmed,
            "cancelled": cancelled,
            "attention": attention,
        }
    except Exception:
        return {"total": 0, "confirmed": 0, "cancelled": 0, "attention": 0}


def mark_resolved(message_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE inbox SET status='resolved' WHERE id=?", (message_id,))
    conn.commit()
    conn.close()


def get_unread_count():
    """Count of messages needing staff attention — used for badge in tab header."""
    try:
        conn  = sqlite3.connect(DB_PATH)
        count = conn.execute(
            "SELECT COUNT(*) FROM inbox WHERE status='needs_attention'"
        ).fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def add_test_message(from_number, body, patient_name="Test Patient", appointment_id=""):
    """Insert a fake incoming message — for testing without a real webhook."""
    intent = "confirmed" if any(w in body.upper() for w in ["CONFIRM","YES","JA","OK"]) \
             else "cancelled" if any(w in body.upper() for w in ["CANCEL","NO"]) \
             else "question"
    status = "resolved" if intent in ("confirmed","cancelled") else "needs_attention"
    conn   = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO inbox (from_number, patient_name, appointment_id, body, intent, status, ts)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (from_number, patient_name, appointment_id, body, intent, status, str(datetime.now())))
    conn.commit()
    conn.close()
