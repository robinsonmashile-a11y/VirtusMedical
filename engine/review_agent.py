"""
CadenceWorks — 5-Star Revenue Builder
Sends automated Google Review requests via WhatsApp after appointments.
"""
import sqlite3
import configparser
import urllib.request
import urllib.parse
import base64
from datetime import datetime, timedelta
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.ini"
DB_PATH     = Path(__file__).parent.parent / "virtus_health.db"

HOURS_AFTER = 2
GOOGLE_REVIEW_LINK = "https://search.google.com/local/writereview?placeid=ChIJI9nRnDxnzB0R8dV4qZ-NKls"

REVIEW_MESSAGE_TEMPLATE = """Hi {patient_name}! 😊

Thank you for visiting *Virtus Health & Medical* today.

We hope you're feeling better. If you have a moment, we'd love to hear about your experience — your feedback helps us improve and helps other patients find us.

⭐ Leave a review here (takes 30 seconds):
{review_link}

Thank you so much!
— Virtus Health & Medical"""


def init_review_table():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("ALTER TABLE bookings ADD COLUMN review_sent INTEGER DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS review_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id TEXT, phone TEXT, patient_name TEXT,
            sent_at TEXT, status TEXT, message TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_due_reviews(hours_after=HOURS_AFTER):
    cutoff = datetime.now() - timedelta(hours=hours_after)
    conn   = sqlite3.connect(DB_PATH)
    rows   = conn.execute("""
        SELECT appointment_id, patient_name, phone, appt_datetime, provider, appointment_type
        FROM bookings
        WHERE phone != '' AND phone != 'nan'
          AND patient_name != '' AND patient_name != 'nan'
          AND (review_sent IS NULL OR review_sent = 0)
          AND appt_datetime <= ?
        ORDER BY appt_datetime ASC
    """, (cutoff.strftime("%Y-%m-%d %H:%M"),)).fetchall()
    conn.close()
    return [{"appointment_id": r[0], "patient_name": r[1], "phone": r[2],
             "appt_datetime": r[3], "provider": r[4], "appointment_type": r[5]} for r in rows]


def mark_review_sent(appointment_id, phone, patient_name, status="sent"):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE bookings SET review_sent=1 WHERE appointment_id=?", (appointment_id,))
    conn.execute("INSERT INTO review_log (appointment_id, phone, patient_name, sent_at, status) VALUES (?,?,?,?,?)",
                 (appointment_id, phone, patient_name, str(datetime.now()), status))
    conn.commit()
    conn.close()


def get_review_stats():
    conn = sqlite3.connect(DB_PATH)
    total_sent = conn.execute("SELECT COUNT(*) FROM review_log WHERE status='sent'").fetchone()[0]
    sent_today = conn.execute("SELECT COUNT(*) FROM review_log WHERE status='sent' AND sent_at >= ?",
                              (datetime.now().strftime("%Y-%m-%d"),)).fetchone()[0]
    try:
        pending = conn.execute("""
            SELECT COUNT(*) FROM bookings
            WHERE phone != '' AND phone != 'nan'
              AND patient_name != '' AND patient_name != 'nan'
              AND (review_sent IS NULL OR review_sent = 0)
              AND appt_datetime <= ?
        """, ((datetime.now() - timedelta(hours=HOURS_AFTER)).strftime("%Y-%m-%d %H:%M"),)).fetchone()[0]
    except Exception:
        pending = 0
    recent = conn.execute("""
        SELECT patient_name, phone, sent_at, status FROM review_log
        ORDER BY sent_at DESC LIMIT 10
    """).fetchall()
    conn.close()
    return {
        "total_sent": total_sent, "sent_today": sent_today, "pending": pending,
        "recent": [{"patient_name": r[0], "phone": r[1], "sent_at": r[2], "status": r[3]} for r in recent],
    }


def load_config():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH)
    return cfg


def is_twilio_configured(cfg):
    sid   = cfg.get("twilio", "account_sid", fallback="")
    token = cfg.get("twilio", "auth_token",  fallback="")
    return sid.startswith("AC") and len(sid) > 10 and token not in ("", "YOUR_AUTH_TOKEN_HERE")


def normalise_phone(phone):
    p = phone.strip().replace(" ", "").replace("-", "")
    if p.startswith("0") and len(p) == 10:
        return "+27" + p[1:]
    if p.startswith("27") and len(p) == 11:
        return "+" + p
    return p


def send_whatsapp(to_number, message, cfg):
    sid      = cfg.get("twilio", "account_sid")
    token    = cfg.get("twilio", "auth_token")
    from_num = cfg.get("twilio", "from_number", fallback="whatsapp:+14155238886")
    to = f"whatsapp:{to_number}" if not to_number.startswith("whatsapp:") else to_number
    url  = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    data = urllib.parse.urlencode({"From": from_num, "To": to, "Body": message}).encode()
    creds = base64.b64encode(f"{sid}:{token}".encode()).decode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Authorization": f"Basic {creds}",
                                          "Content-Type": "application/x-www-form-urlencoded"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def build_review_message(patient_name, review_link=GOOGLE_REVIEW_LINK):
    first_name = patient_name.strip().split()[0].title() if patient_name else "there"
    return REVIEW_MESSAGE_TEMPLATE.format(patient_name=first_name, review_link=review_link)


def run_review_agent(cfg=None, dry_run=False, hours_after=HOURS_AFTER, review_link=GOOGLE_REVIEW_LINK):
    init_review_table()
    if cfg is None:
        cfg = load_config()
    live = is_twilio_configured(cfg) and not dry_run
    due  = get_due_reviews(hours_after)
    results = {"checked": len(due), "sent": 0, "errors": 0, "dry_run": not live, "details": []}
    for appt in due:
        phone   = normalise_phone(appt["phone"])
        name    = appt["patient_name"]
        appt_id = appt["appointment_id"]
        message = build_review_message(name, review_link)
        if not live:
            mark_review_sent(appt_id, phone, name, status="dry_run")
            results["sent"] += 1
            results["details"].append({"patient_name": name, "phone": phone,
                                        "status": "dry_run", "appt_datetime": appt["appt_datetime"]})
        else:
            result = send_whatsapp(phone, message, cfg)
            status = "sent" if result.get("success") else "error"
            mark_review_sent(appt_id, phone, name, status=status)
            if result.get("success"):
                results["sent"] += 1
            else:
                results["errors"] += 1
            results["details"].append({"patient_name": name, "phone": phone,
                                        "status": status, "appt_datetime": appt["appt_datetime"]})
    return results
