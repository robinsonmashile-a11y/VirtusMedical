"""
CadenceWorks — Reminder Agent
=============================
Watches the live booking database for upcoming high/medium risk appointments
and fires WhatsApp reminders via Twilio at the right time.

Runs as a background loop — called from the Streamlit app or standalone:
    python -m engine.reminder_agent

MODES:
  - DRY RUN (default when Twilio not configured): logs what it WOULD send
  - LIVE: sends real WhatsApp messages via Twilio
"""

import sqlite3
import configparser
import json
import time
import urllib.request
import urllib.parse
import base64
from datetime import datetime, timedelta
from pathlib import Path


CONFIG_PATH = Path(__file__).parent.parent / "config.ini"
DB_PATH     = Path(__file__).parent.parent / "virtus_health.db"


# ── Config loader ──────────────────────────────────────────────────────────────

def load_config():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH)
    return cfg


def is_twilio_configured(cfg):
    sid   = cfg.get("twilio", "account_sid", fallback="")
    token = cfg.get("twilio", "auth_token",  fallback="")
    return (sid.startswith("AC") and len(sid) > 10 and
            token not in ("", "YOUR_AUTH_TOKEN_HERE") and
            sid != "YOUR_ACCOUNT_SID_HERE")


# ── Message builder ────────────────────────────────────────────────────────────

def build_message(template_key, cfg, appt: dict) -> str:
    """Fill in a message template with appointment details."""
    raw = cfg.get("templates", template_key, fallback="Reminder for your appointment.")

    # Clean up multiline ini value
    lines = [l.strip() for l in raw.strip().splitlines()]
    template = "\n".join(lines)

    appt_dt = appt.get("appt_datetime")
    if isinstance(appt_dt, str):
        try:
            appt_dt = datetime.fromisoformat(appt_dt)
        except Exception:
            appt_dt = None

    replacements = {
        "{practice_name}": cfg.get("practice", "name", fallback="Your Practice"),
        "{patient_name}":  appt.get("patient_name", "there"),
        "{provider}":      appt.get("provider", "your doctor"),
        "{appt_date}":     appt_dt.strftime("%A %d %B").replace(" 0", " ") if appt_dt else "your appointment date",
        "{appt_time}":     appt_dt.strftime("%H:%M") if appt_dt else "your appointment time",
        "{appt_type}":     appt.get("appointment_type", "appointment"),
        "{hours_until}":   str(appt.get("hours_until", "")),
        "{cancel_number}": cfg.get("templates", "cancel_number", fallback="us"),
    }

    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)

    return template


# ── Twilio sender ──────────────────────────────────────────────────────────────

def send_whatsapp(to_number: str, message: str, cfg) -> dict:
    """
    Send a WhatsApp message via Twilio REST API.
    Returns {"success": True/False, "sid": ..., "error": ...}
    """
    sid      = cfg.get("twilio", "account_sid")
    token    = cfg.get("twilio", "auth_token")
    from_num = cfg.get("twilio", "from_number", fallback="whatsapp:+14155238886")

    # Ensure number is in WhatsApp format
    if not to_number.startswith("whatsapp:"):
        country = cfg.get("practice", "country_code", fallback="+27")
        # Strip leading 0 if present and prepend country code
        clean = to_number.lstrip("+").lstrip("0")
        if not clean.startswith(country.lstrip("+")):
            clean = country.lstrip("+") + clean
        to_number = f"whatsapp:+{clean}"

    url  = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    data = urllib.parse.urlencode({
        "From": from_num,
        "To":   to_number,
        "Body": message,
    }).encode()

    credentials = base64.b64encode(f"{sid}:{token}".encode()).decode()
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type":  "application/x-www-form-urlencoded",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            return {"success": True, "sid": result.get("sid"), "error": None}
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return {"success": False, "sid": None, "error": f"HTTP {e.code}: {body}"}
    except Exception as ex:
        return {"success": False, "sid": None, "error": str(ex)}


# ── Reminder DB helpers ────────────────────────────────────────────────────────

def init_reminder_tables():
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS reminder_queue (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id  TEXT,
            patient_number  TEXT,
            patient_name    TEXT,
            provider        TEXT,
            appt_datetime   TEXT,
            appointment_type TEXT,
            risk_score      REAL,
            risk_band       TEXT,
            reminder_type   TEXT,    -- '72hr' | '24hr' | '4hr'
            scheduled_for   TEXT,    -- ISO datetime to send
            sent            INTEGER DEFAULT 0,
            sent_at         TEXT,
            message_sid     TEXT,
            dry_run         INTEGER DEFAULT 1,
            created_at      TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS reminder_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id  TEXT,
            reminder_type   TEXT,
            patient_number  TEXT,
            message_preview TEXT,
            status          TEXT,    -- 'sent' | 'dry_run' | 'failed'
            error           TEXT,
            ts              TEXT
        )
    """)

    conn.commit()
    conn.close()


def schedule_reminders(appt: dict, cfg, dry_run: bool = True):
    """
    Given a scored appointment, create reminder_queue entries for it.
    Only schedules reminders that are still in the future.
    """
    risk_score = appt.get("risk_score", 0)
    high_thresh = float(cfg.get("reminder_agent", "high_risk_threshold",  fallback=70))
    med_thresh  = float(cfg.get("reminder_agent", "medium_risk_threshold", fallback=45))

    if risk_score >= high_thresh:
        schedules_hours = [72, 24, 4]
    elif risk_score >= med_thresh:
        schedules_hours = [24]
    else:
        return 0   # Low risk — no reminder needed

    appt_dt_str = appt.get("appt_datetime", "")
    try:
        appt_dt = datetime.fromisoformat(str(appt_dt_str))
    except Exception:
        return 0

    now       = datetime.now()
    scheduled = 0
    conn      = sqlite3.connect(DB_PATH)
    c         = conn.cursor()

    for hours in schedules_hours:
        send_at = appt_dt - timedelta(hours=hours)
        if send_at <= now:
            continue   # Already past — skip

        reminder_type = f"{hours}hr"

        # Check not already scheduled
        existing = c.execute(
            "SELECT id FROM reminder_queue WHERE appointment_id=? AND reminder_type=?",
            (appt.get("appointment_id"), reminder_type)
        ).fetchone()
        if existing:
            continue

        c.execute("""
            INSERT INTO reminder_queue
            (appointment_id, patient_number, patient_name, provider,
             appt_datetime, appointment_type, risk_score, risk_band,
             reminder_type, scheduled_for, dry_run, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            appt.get("appointment_id"),
            appt.get("patient_number", ""),
            appt.get("patient_name", "Patient"),
            appt.get("provider", ""),
            str(appt_dt),
            appt.get("appointment_type", "Consult"),
            risk_score,
            appt.get("risk_band", ""),
            reminder_type,
            str(send_at),
            int(dry_run),
            str(now),
        ))
        scheduled += 1

    conn.commit()
    conn.close()
    return scheduled


def get_due_reminders():
    """Fetch reminders that are due to be sent right now."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT * FROM reminder_queue
        WHERE sent = 0
          AND scheduled_for <= datetime('now', 'localtime')
        ORDER BY scheduled_for ASC
    """).fetchall()
    cols = [d[0] for d in conn.execute("PRAGMA table_info(reminder_queue)").fetchall()]
    conn.close()
    return [dict(zip(cols, r)) for r in rows]


def mark_sent(queue_id: int, sid: str = None, dry_run: bool = True):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        UPDATE reminder_queue
        SET sent=1, sent_at=?, message_sid=?, dry_run=?
        WHERE id=?
    """, (str(datetime.now()), sid, int(dry_run), queue_id))
    conn.commit()
    conn.close()


def log_reminder(appt_id, reminder_type, number, preview, status, error=None):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO reminder_log
        (appointment_id, reminder_type, patient_number, message_preview, status, error, ts)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (appt_id, reminder_type, number, preview[:200], status,
          error, str(datetime.now())))
    conn.commit()
    conn.close()


def get_reminder_queue(limit=100):
    """Return queue as DataFrame for display."""
    import pandas as pd
    conn = sqlite3.connect(DB_PATH)
    df   = pd.read_sql_query("""
        SELECT appointment_id, patient_name, provider, appt_datetime,
               risk_score, risk_band, reminder_type, scheduled_for,
               sent, sent_at, dry_run
        FROM reminder_queue
        ORDER BY scheduled_for ASC
        LIMIT ?
    """, conn, params=(limit,))
    conn.close()
    return df


def get_reminder_log(limit=50):
    import pandas as pd
    conn = sqlite3.connect(DB_PATH)
    df   = pd.read_sql_query("""
        SELECT ts, appointment_id, reminder_type, patient_number,
               message_preview, status, error
        FROM reminder_log
        ORDER BY id DESC
        LIMIT ?
    """, conn, params=(limit,))
    conn.close()
    return df


def get_reminder_stats():
    conn   = sqlite3.connect(DB_PATH)
    c      = conn.cursor()
    stats  = {}
    stats["queued"]    = c.execute("SELECT COUNT(*) FROM reminder_queue WHERE sent=0").fetchone()[0]
    stats["sent"]      = c.execute("SELECT COUNT(*) FROM reminder_queue WHERE sent=1").fetchone()[0]
    stats["dry_runs"]  = c.execute("SELECT COUNT(*) FROM reminder_queue WHERE sent=1 AND dry_run=1").fetchone()[0]
    stats["live_sent"] = c.execute("SELECT COUNT(*) FROM reminder_queue WHERE sent=1 AND dry_run=0").fetchone()[0]
    stats["failed"]    = c.execute("SELECT COUNT(*) FROM reminder_log WHERE status='failed'").fetchone()[0]
    conn.close()
    return stats


# ── Main agent loop ────────────────────────────────────────────────────────────

def run_once(verbose=True) -> list:
    """
    Run one cycle of the Reminder Agent.
    - Checks for due reminders
    - Sends or dry-runs them
    - Returns list of actions taken
    """
    cfg      = load_config()
    live     = is_twilio_configured(cfg)
    dry_run  = not live
    actions  = []

    due = get_due_reminders()

    if not due:
        if verbose:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Reminder Agent: nothing due.")
        return actions

    for reminder in due:
        appt = {
            "appointment_id":   reminder["appointment_id"],
            "patient_name":     reminder.get("patient_name", "there"),
            "provider":         reminder.get("provider", "your doctor"),
            "appt_datetime":    reminder.get("appt_datetime"),
            "appointment_type": reminder.get("appointment_type", "appointment"),
            "hours_until":      reminder.get("reminder_type", "").replace("hr", ""),
        }

        template_key = f"reminder_{reminder['reminder_type']}"
        message      = build_message(template_key, cfg, appt)
        to_number    = reminder.get("patient_number", "")
        queue_id     = reminder["id"]

        if dry_run or not to_number:
            # DRY RUN — log but don't send
            status = "dry_run"
            mark_sent(queue_id, sid="DRY_RUN", dry_run=True)
            log_reminder(
                reminder["appointment_id"],
                reminder["reminder_type"],
                to_number or "(no number)",
                message,
                "dry_run"
            )
            action = {
                "appointment_id": reminder["appointment_id"],
                "reminder_type":  reminder["reminder_type"],
                "status":         "dry_run",
                "message":        message,
                "to":             to_number or "(no number on file)",
            }

        else:
            # LIVE — send via Twilio
            result = send_whatsapp(to_number, message, cfg)
            if result["success"]:
                status = "sent"
                mark_sent(queue_id, sid=result["sid"], dry_run=False)
                log_reminder(reminder["appointment_id"], reminder["reminder_type"],
                             to_number, message, "sent")
            else:
                status = "failed"
                log_reminder(reminder["appointment_id"], reminder["reminder_type"],
                             to_number, message, "failed", error=result["error"])

            action = {
                "appointment_id": reminder["appointment_id"],
                "reminder_type":  reminder["reminder_type"],
                "status":         status,
                "message":        message,
                "to":             to_number,
                "sid":            result.get("sid"),
                "error":          result.get("error"),
            }

        actions.append(action)
        if verbose:
            icon = "✉" if status == "sent" else ("📋" if status == "dry_run" else "✗")
            print(f"  {icon} [{status.upper()}] {reminder['appointment_id']} "
                  f"· {reminder['reminder_type']} → {to_number or '(no number)'}")

    return actions


def run_loop(interval_minutes: int = 15):
    """Continuous loop — runs every interval_minutes. Call from CLI."""
    print(f"\n{'='*55}")
    print("  CadenceWorks — Reminder Agent")
    print(f"{'='*55}")
    cfg  = load_config()
    live = is_twilio_configured(cfg)
    print(f"  Mode:     {'🟢 LIVE (Twilio connected)' if live else '🟡 DRY RUN (Twilio not configured)'}")
    print(f"  Interval: every {interval_minutes} minutes")
    print(f"  Config:   {CONFIG_PATH}")
    print(f"{'='*55}\n")

    while True:
        try:
            actions = run_once(verbose=True)
            if actions:
                print(f"  → {len(actions)} reminder(s) processed\n")
        except Exception as e:
            print(f"  ✗ Agent error: {e}")
        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    init_reminder_tables()
    run_loop()
