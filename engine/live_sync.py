"""
CadenceWorks — Live Sync / Booking Store
Single source of truth for all live bookings.
Score New Bookings, Live Monitor and Reminder Agent all read/write here.
"""

import sqlite3
import hashlib
import pandas as pd
from pathlib import Path
from datetime import datetime

from engine.predictive import _build_features, _rule_based_score
from engine import ingestor

DB_PATH   = Path("virtus_health.db")
WATCH_DIR = Path("watch_folder")


# ── DB init ────────────────────────────────────────────────────────────────────

def init_db():
    WATCH_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id   TEXT,
            patient_name     TEXT DEFAULT '',
            phone            TEXT DEFAULT '',
            appt_datetime    TEXT DEFAULT '',
            provider         TEXT,
            patient_type     TEXT,
            channel          TEXT,
            day_of_week      TEXT,
            lead_time_days   INTEGER,
            appointment_type TEXT,
            is_prime_slot    INTEGER,
            fee              REAL,
            risk_score       REAL,
            risk_band        TEXT,
            recommended_action TEXT,
            status           TEXT DEFAULT 'Pending',
            source           TEXT,
            scored_at        TEXT,
            reminded         INTEGER DEFAULT 0,
            reminder_sent_48hr INTEGER DEFAULT 0,
            reminder_sent_2hr  INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS sync_log (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            event  TEXT,
            detail TEXT,
            ts     TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS processed_files (
            filepath     TEXT PRIMARY KEY,
            file_hash    TEXT,
            processed_at TEXT,
            rows_scored  INTEGER
        )
    """)
    # ── Conversation log — every WhatsApp message both directions ─────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS conversation_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            phone           TEXT NOT NULL,
            direction       TEXT NOT NULL CHECK(direction IN ('inbound','outbound')),
            message         TEXT NOT NULL,
            ts              TEXT NOT NULL,
            booking_id      TEXT DEFAULT NULL,
            outcome         TEXT DEFAULT 'in_progress'
                            CHECK(outcome IN ('in_progress','booking_made','no_booking'))
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_conv_phone ON conversation_log(phone)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_conv_id    ON conversation_log(conversation_id)")
    conn.commit()
    conn.close()


# ── Conversation logging ───────────────────────────────────────────────────────

def log_message(phone: str, direction: str, message: str,
                conversation_id: str = None, booking_id: str = None,
                outcome: str = "in_progress"):
    """
    Write a single WhatsApp message (either direction) to conversation_log.
    conversation_id defaults to the phone number so all messages from the
    same number in the same session group naturally.
    """
    conv_id = conversation_id or phone
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO conversation_log
            (conversation_id, phone, direction, message, ts, booking_id, outcome)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        conv_id, phone, direction, message,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        booking_id, outcome
    ))
    conn.commit()
    conn.close()


def resolve_conversation(phone: str, outcome: str, booking_id: str = None):
    """
    Mark all in_progress messages for this phone as resolved.
    outcome: 'booking_made' or 'no_booking'
    Also stamps the booking_id on every row if provided.
    """
    conn = sqlite3.connect(DB_PATH)
    if booking_id:
        conn.execute("""
            UPDATE conversation_log
               SET outcome = ?, booking_id = ?
             WHERE phone = ? AND outcome = 'in_progress'
        """, (outcome, booking_id, phone))
    else:
        conn.execute("""
            UPDATE conversation_log
               SET outcome = ?
             WHERE phone = ? AND outcome = 'in_progress'
        """, (outcome, phone))
    conn.commit()
    conn.close()


def get_resolved_booking_id(phone: str):
    """Return the booking_id if this phone has a resolved booking, else None."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT booking_id FROM conversation_log WHERE phone=? AND outcome='booking_made' "
        "AND booking_id IS NOT NULL AND booking_id != '' ORDER BY ts DESC LIMIT 1",
        (phone,)
    ).fetchone()
    conn.close()
    return row[0] if row else None


def get_conversations(limit: int = 100) -> pd.DataFrame:
    """
    Return one row per conversation (latest message per phone),
    plus message count, outcome and booking_id.
    """
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT
            conversation_id,
            phone,
            COUNT(*)                                    AS message_count,
            MIN(ts)                                     AS started_at,
            MAX(ts)                                     AS last_message_at,
            MAX(CASE WHEN direction='inbound'
                     THEN message END)                  AS last_patient_message,
            MAX(booking_id)                             AS booking_id,
            MAX(outcome)                                AS outcome
        FROM conversation_log
        GROUP BY conversation_id
        ORDER BY last_message_at DESC
        LIMIT ?
    """, conn, params=(limit,))
    conn.close()
    return df


def get_conversation_thread(conversation_id: str) -> pd.DataFrame:
    """
    Return the full message-by-message thread for one conversation,
    oldest first.
    """
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT direction, message, ts, booking_id, outcome
          FROM conversation_log
         WHERE conversation_id = ?
         ORDER BY ts ASC, id ASC
    """, conn, params=(conversation_id,))
    conn.close()
    return df


def get_conversation_stats() -> dict:
    """Summary stats for the Tab 8 header strip."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("""
        SELECT
            COUNT(DISTINCT conversation_id)                          AS total,
            SUM(CASE WHEN outcome='booking_made'  THEN 1 ELSE 0 END) AS booked,
            SUM(CASE WHEN outcome='no_booking'    THEN 1 ELSE 0 END) AS no_booking,
            SUM(CASE WHEN outcome='in_progress'   THEN 1 ELSE 0 END) AS in_progress
        FROM (
            SELECT conversation_id, MAX(outcome) AS outcome
              FROM conversation_log
             GROUP BY conversation_id
        )
    """).fetchone()
    conn.close()
    if not row or row[0] == 0:
        return {"total": 0, "booked": 0, "no_booking": 0, "in_progress": 0, "conversion_rate": 0}
    total = row[0] or 0
    booked = row[1] or 0
    return {
        "total":           total,
        "booked":          booked,
        "no_booking":      row[2] or 0,
        "in_progress":     row[3] or 0,
        "conversion_rate": round(booked / total * 100) if total else 0,
    }


def log_event(event, detail=""):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO sync_log (event, detail, ts) VALUES (?,?,?)",
        (event, detail, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()


# ── Scoring ────────────────────────────────────────────────────────────────────

def _band(s):
    if s >= 70: return "High Risk"
    if s >= 45: return "Medium Risk"
    return "Low Risk"

def _action(s):
    if s >= 70: return "Send reminders at 48hr & 2hr"
    if s >= 45: return "Send reminder at 48hr"
    return "Standard reminder only"

def score_dataframe(df, source="upload"):
    """Score a UDM dataframe and return rows ready for the bookings table."""
    features = _build_features(df)
    scores   = features.apply(_rule_based_score, axis=1).values
    now      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for i, (_, row) in enumerate(df.iterrows()):
        s = round(float(scores[i]), 1)
        # Build appt_datetime — combine date + time if both present
        appt_dt = ""
        if "appointment_date" in row and row["appointment_date"]:
            try:
                date_part = pd.to_datetime(row["appointment_date"]).strftime("%Y-%m-%d")
                # Try to get time from appointment_time column if available
                time_part = "09:00"
                for time_col in ["appointment_time", "appt_time", "time"]:
                    if time_col in row and row[time_col]:
                        t_val = str(row[time_col]).strip()
                        # Handle various time formats: "09:00", "09:00:00", "0900"
                        if len(t_val) >= 4 and ":" in t_val:
                            time_part = t_val[:5]
                        elif len(t_val) == 4 and t_val.isdigit():
                            time_part = f"{t_val[:2]}:{t_val[2:]}"
                        break
                appt_dt = f"{date_part} {time_part}"
            except Exception:
                pass
        rows.append({
            "appointment_id":    str(row.get("appointment_id", f"APT-{i+1:04d}")),
            "patient_name":      str(row.get("patient_name", "")),
            "phone":             str(row.get("phone", "")),
            "appt_datetime":     appt_dt,
            "provider":          str(row.get("provider", "")),
            "patient_type":      str(row.get("patient_type", "")),
            "channel":           str(row.get("channel", "")),
            "day_of_week":       str(row.get("day_of_week", "")),
            "lead_time_days":    int(row.get("lead_time_days", 0)),
            "appointment_type":  str(row.get("appointment_type", "")),
            "is_prime_slot":     int(bool(row.get("is_prime_slot", False))),
            "fee":               float(row.get("fee", 0)),
            "risk_score":        s,
            "risk_band":         _band(s),
            "recommended_action": _action(s),
            "status":            str(row.get("status", "Pending")),
            "source":            source,
            "scored_at":         now,
            "reminded":          0,
            "reminder_sent_48hr": 0,
            "reminder_sent_2hr":  0,
        })
    return rows


def insert_bookings(rows):
    """Insert scored bookings, skipping duplicates by appointment_id alone."""
    if not rows:
        return 0
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    inserted = 0
    for r in rows:
        existing = c.execute(
            "SELECT id FROM bookings WHERE appointment_id=?",
            (r["appointment_id"],)
        ).fetchone()
        if not existing:
            c.execute("""
                INSERT INTO bookings
                (appointment_id, patient_name, phone, appt_datetime,
                 provider, patient_type, channel, day_of_week,
                 lead_time_days, appointment_type, is_prime_slot, fee,
                 risk_score, risk_band, recommended_action, status,
                 source, scored_at, reminded, reminder_sent_48hr, reminder_sent_2hr)
                VALUES
                (:appointment_id, :patient_name, :phone, :appt_datetime,
                 :provider, :patient_type, :channel, :day_of_week,
                 :lead_time_days, :appointment_type, :is_prime_slot, :fee,
                 :risk_score, :risk_band, :recommended_action, :status,
                 :source, :scored_at, :reminded, :reminder_sent_48hr, :reminder_sent_2hr)
            """, r)
            inserted += 1
    conn.commit()
    conn.close()
    return inserted


def add_manual_booking(appt: dict) -> int:
    """
    Add a single manually-entered booking (from Score New Bookings tab).
    appt must have: appointment_id, patient_name, phone, appt_datetime,
                    provider, appointment_type, lead_time_days, fee
    Returns 1 if inserted, 0 if duplicate.
    """
    from engine.predictive import _rule_based_score
    import numpy as np

    # Build a one-row DataFrame to score it properly
    now = datetime.now()
    try:
        appt_dt = datetime.strptime(appt["appt_datetime"], "%Y-%m-%d %H:%M")
        lead    = max(0, (appt_dt.date() - now.date()).days)
        dow     = appt_dt.strftime("%A")
        hour    = appt_dt.hour
        prime   = 1 if 8 <= hour <= 12 else 0
    except Exception:
        lead, dow, prime = int(appt.get("lead_time_days", 0)), "", 0

    row = {
        "appointment_id":   appt["appointment_id"],
        "patient_name":     appt.get("patient_name", ""),
        "phone":            appt.get("phone", ""),
        "appt_datetime":    appt.get("appt_datetime", ""),
        "provider":         appt.get("provider", ""),
        "patient_type":     appt.get("patient_type", "Existing"),
        "channel":          appt.get("channel", "Manual"),
        "day_of_week":      dow,
        "lead_time_days":   lead,
        "appointment_type": appt.get("appointment_type", "Consultation"),
        "is_prime_slot":    prime,
        "fee":              float(appt.get("fee", 500)),
        "status":           "Pending",
        "source":           appt.get("source", "manual"),
        "scored_at":        now.strftime("%Y-%m-%d %H:%M:%S"),
        "reminded":         0,
        "reminder_sent_48hr": 0,
        "reminder_sent_2hr":  0,
    }

    # Score it
    df_single = pd.DataFrame([{
        "patient_type":     row["patient_type"],
        "channel":          row["channel"],
        "day_of_week":      row["day_of_week"],
        "lead_time_days":   row["lead_time_days"],
        "appointment_type": row["appointment_type"],
        "is_prime_slot":    row["is_prime_slot"],
    }])
    try:
        features = _build_features(df_single)
        score = round(float(_rule_based_score(features.iloc[0])), 1)
    except Exception:
        score = 30.0

    row["risk_score"]         = score
    row["risk_band"]          = _band(score)
    row["recommended_action"] = _action(score)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    existing = c.execute(
        "SELECT id FROM bookings WHERE appointment_id=? AND source='manual'",
        (row["appointment_id"],)
    ).fetchone()
    if not existing:
        c.execute("""
            INSERT INTO bookings
            (appointment_id, patient_name, phone, appt_datetime,
             provider, patient_type, channel, day_of_week,
             lead_time_days, appointment_type, is_prime_slot, fee,
             risk_score, risk_band, recommended_action, status,
             source, scored_at, reminded, reminder_sent_48hr, reminder_sent_2hr)
            VALUES
            (:appointment_id, :patient_name, :phone, :appt_datetime,
             :provider, :patient_type, :channel, :day_of_week,
             :lead_time_days, :appointment_type, :is_prime_slot, :fee,
             :risk_score, :risk_band, :recommended_action, :status,
             :source, :scored_at, :reminded, :reminder_sent_48hr, :reminder_sent_2hr)
        """, row)
        conn.commit()
        conn.close()
        log_event("MANUAL_BOOKING", f"{row['appointment_id']} — {row['patient_name']} — {row['risk_band']}")
        return 1
    conn.close()
    return 0


# ── File ingestion ─────────────────────────────────────────────────────────────

def _file_hash(filepath):
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        h.update(f.read())
    return h.hexdigest()

def _already_processed(filepath, file_hash):
    conn = sqlite3.connect(DB_PATH)
    # Check file hash
    row = conn.execute(
        "SELECT file_hash FROM processed_files WHERE filepath=?", (str(filepath),)
    ).fetchone()
    if not row or row[0] != file_hash:
        conn.close()
        return False
    # Even if hash matches, check if bookings actually exist for this source
    # (handles case where DB was cleared but processed_files wasn't)
    source = Path(filepath).name
    count = conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE source=?", (source,)
    ).fetchone()[0]
    conn.close()
    return count > 0

def _mark_processed(filepath, file_hash, rows_scored):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO processed_files (filepath, file_hash, processed_at, rows_scored) VALUES (?,?,?,?)",
        (str(filepath), file_hash, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), rows_scored)
    )
    conn.commit()
    conn.close()

def ingest_file(filepath, source_label=None):
    """Ingest a single file path into the bookings DB. Returns rows inserted."""
    fp = Path(filepath)
    source = source_label or fp.name
    fh = _file_hash(fp)
    if _already_processed(fp, fh):
        return 0
    df, _ = ingestor.ingest(fp)
    rows = score_dataframe(df, source=source)
    n = insert_bookings(rows)
    _mark_processed(fp, fh, n)
    log_event("FILE_INGESTED", f"{fp.name} → {n} bookings scored")
    return n

def ingest_bytes(file_bytes, file_name):
    """Ingest uploaded file bytes. Deletes any existing bookings from this source first,
    then re-inserts fresh — so uploading the same file always works."""
    import tempfile, os
    suffix = Path(file_name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        fp = Path(tmp_path)
        if fp.suffix in [".xlsx", ".xls"]:
            raw = pd.read_excel(fp)
        else:
            raw = pd.read_csv(fp)
        raw.columns = [c.strip().lower().replace(" ", "_") for c in raw.columns]

        df, _ = ingestor.ingest(fp)

        for extra_col, raw_aliases in [
            ("patient_name",     ["patient_name", "patient", "name", "client_name"]),
            ("phone",            ["phone", "phone_number", "mobile", "contact", "cell"]),
            ("appointment_time", ["appointment_time", "appt_time", "time", "slot_time"]),
        ]:
            for alias in raw_aliases:
                if alias in raw.columns and len(raw) == len(df):
                    df[extra_col] = raw[alias].fillna("").astype(str)
                    break

        # Remove any existing bookings from this source so re-upload always works
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM bookings WHERE source=?", (file_name,))
        conn.commit()
        conn.close()

        rows = score_dataframe(df, source=file_name)
        n = insert_bookings(rows)
        log_event("FILE_INGESTED", f"{file_name} → {n} bookings scored")
        return n
    finally:
        os.unlink(tmp_path)

def ingest_file_with_extras(filepath, source_label=None):
    """
    Ingest a file and also capture patient_name, phone, appointment_time
    from raw columns that the UDM ingestor drops.
    """
    fp = Path(filepath)
    source = source_label or fp.name
    fh = _file_hash(fp)
    if _already_processed(fp, fh):
        return 0

    # Read raw first to get optional extra columns
    if fp.suffix in [".xlsx", ".xls"]:
        raw = pd.read_excel(fp)
    else:
        raw = pd.read_csv(fp)

    raw.columns = [c.strip().lower().replace(" ", "_") for c in raw.columns]

    # Run UDM ingest
    df, _ = ingestor.ingest(fp)

    # Stitch extra columns back if present in raw
    for extra_col, raw_aliases in [
        ("patient_name", ["patient_name", "patient", "name", "client_name"]),
        ("phone",        ["phone", "phone_number", "mobile", "contact", "cell"]),
        ("appointment_time", ["appointment_time", "appt_time", "time", "slot_time"]),
    ]:
        for alias in raw_aliases:
            if alias in raw.columns:
                if len(raw) == len(df):
                    df[extra_col] = raw[alias].fillna("").astype(str)
                break

    rows = score_dataframe(df, source=source)
    n = insert_bookings(rows)
    _mark_processed(fp, fh, n)
    log_event("FILE_INGESTED", f"{fp.name} → {n} bookings scored")
    return n

def scan_watch_folder():
    WATCH_DIR.mkdir(exist_ok=True)
    files = list(WATCH_DIR.glob("*.xlsx")) + \
            list(WATCH_DIR.glob("*.xls"))  + \
            list(WATCH_DIR.glob("*.csv"))
    files_done, bookings_done = 0, 0
    for fp in files:
        try:
            n = ingest_file(fp)
            if n > 0:
                files_done += 1
                bookings_done += n
        except Exception as e:
            log_event("FILE_ERROR", f"{fp.name}: {e}")
    return files_done, bookings_done


# ── Read from DB ───────────────────────────────────────────────────────────────

def get_future_bookings(limit=500):
    """Fetch only bookings with appt_datetime >= now, most urgent first."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT * FROM bookings
        WHERE appt_datetime >= ?
        ORDER BY appt_datetime ASC, risk_score DESC
        LIMIT ?
    """, conn, params=(now_str, limit))
    conn.close()
    return df

def get_live_bookings(limit=500, risk_band=None):
    conn = sqlite3.connect(DB_PATH)
    if risk_band:
        df = pd.read_sql_query(
            "SELECT * FROM bookings WHERE risk_band=? ORDER BY scored_at DESC, risk_score DESC LIMIT ?",
            conn, params=(risk_band, limit)
        )
    else:
        df = pd.read_sql_query(
            "SELECT * FROM bookings ORDER BY scored_at DESC, risk_score DESC LIMIT ?",
            conn, params=(limit,)
        )
    conn.close()
    return df

def get_pending_reminders():
    """Bookings that need reminders and have a real appt_datetime."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT * FROM bookings
        WHERE risk_band IN ('High Risk','Medium Risk')
          AND status = 'Pending'
          AND appt_datetime != ''
        ORDER BY appt_datetime ASC
    """, conn)
    conn.close()
    return df

def get_live_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    stats = {}
    stats["total"]          = c.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
    stats["high_risk"]      = c.execute("SELECT COUNT(*) FROM bookings WHERE risk_band='High Risk'").fetchone()[0]
    stats["medium_risk"]    = c.execute("SELECT COUNT(*) FROM bookings WHERE risk_band='Medium Risk'").fetchone()[0]
    stats["low_risk"]       = c.execute("SELECT COUNT(*) FROM bookings WHERE risk_band='Low Risk'").fetchone()[0]
    stats["pending_reminders"] = c.execute(
        "SELECT COUNT(*) FROM bookings WHERE risk_band IN ('High Risk','Medium Risk') AND reminded=0"
    ).fetchone()[0]
    last = c.execute("SELECT ts FROM sync_log ORDER BY id DESC LIMIT 1").fetchone()
    stats["last_sync"] = last[0] if last else "Never"
    rev = c.execute("SELECT SUM(fee) FROM bookings WHERE risk_band='High Risk'").fetchone()[0]
    stats["revenue_at_risk"] = float(rev) if rev else 0.0
    conn.close()
    return stats

def get_sync_log(limit=30):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT ts, event, detail FROM sync_log ORDER BY id DESC LIMIT ?",
        conn, params=(limit,)
    )
    conn.close()
    return df

def mark_reminded(appointment_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE bookings SET reminded=1 WHERE appointment_id=?", (appointment_id,))
    conn.commit()
    conn.close()

def mark_reminder_sent(appointment_id, reminder_type):
    col = "reminder_sent_48hr" if "48" in reminder_type else "reminder_sent_2hr"
    conn = sqlite3.connect(DB_PATH)
    conn.execute(f"UPDATE bookings SET {col}=1, reminded=1 WHERE appointment_id=?", (appointment_id,))
    conn.commit()
    conn.close()

def delete_booking(appointment_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM bookings WHERE appointment_id=?", (appointment_id,))
    conn.commit()
    conn.close()

def clear_all():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM bookings")
    conn.execute("DELETE FROM sync_log")
    conn.execute("DELETE FROM processed_files")
    conn.commit()
    conn.close()
    log_event("DB_CLEARED", "All bookings and file history wiped — ready for fresh uploads")


def update_booking_status(appointment_id, status):
    """Update the status of a booking — e.g. Confirmed, Cancelled."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE bookings SET status=? WHERE appointment_id=?",
        (status, appointment_id)
    )
    conn.commit()
    conn.close()
    log_event("STATUS_UPDATE", f"{appointment_id} → {status}")
