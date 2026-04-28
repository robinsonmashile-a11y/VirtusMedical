"""
CadenceWorks — Virtus Health & Medical Triage Agent
==========================================
Handles inbound WhatsApp messages on Virtus Health's practice number.
Specifically handles:
  - House call requests
  - Tele-consult requests
  - FAQs about these two services
  - Emergency detection and escalation
  - Deflection of all other service enquiries

Flow per conversation:
  idle          → patient messages, intent detected
  faq           → answering questions, offering to move to booking
  triage        → clarifying house call vs tele-consult
  collect_name  → collecting patient full name
  collect_phone → collecting contact number
  collect_address → collecting address (house call only)
  collect_complaint → collecting reason/symptoms
  collect_time  → collecting preferred time
  confirm       → showing summary, awaiting YES
  notified      → request sent to doctor, conversation complete

All state persists in SQLite so it survives restarts.
Doctor notification and patient confirmation fire after YES.
"""

import sqlite3
import json
import configparser
import re
from datetime import datetime
from pathlib import Path

from engine.virtus_health_knowledge import (
    PRACTICE,
    FAQS,
)
from engine.fluid_medical_knowledge import (
    HOUSE_CALL_KEYWORDS,
    TELE_CONSULT_KEYWORDS,
    EMERGENCY_KEYWORDS,
    DEFLECT_KEYWORDS,
    build_doctor_notification,
    build_patient_confirmation,
)

BASE_DIR    = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "config.ini"
DB_PATH     = BASE_DIR / "virtus_health.db"


# ── DB helpers ─────────────────────────────────────────────────────────────────

def init_triage_table():
    """Create the triage_conversations table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS triage_conversations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            phone       TEXT UNIQUE,
            state       TEXT DEFAULT 'idle',
            service     TEXT DEFAULT '',
            data        TEXT DEFAULT '{}',
            updated_at  TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS triage_requests (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id   TEXT UNIQUE,
            phone        TEXT,
            service_type TEXT,
            patient_name TEXT,
            address      TEXT,
            complaint    TEXT,
            preferred_time TEXT,
            status       TEXT DEFAULT 'pending',
            created_at   TEXT,
            notified_at  TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_triage_state(phone):
    """Get conversation state and data for a phone number."""
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute(
        "SELECT state, service, data FROM triage_conversations WHERE phone=?",
        (phone,)
    ).fetchone()
    conn.close()
    if row:
        return row[0], row[1], json.loads(row[2] or "{}")
    return "idle", "", {}


def set_triage_state(phone, state, service="", data=None):
    """Save conversation state."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO triage_conversations (phone, state, service, data, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(phone) DO UPDATE SET
            state=excluded.state,
            service=excluded.service,
            data=excluded.data,
            updated_at=excluded.updated_at
    """, (phone, state, service, json.dumps(data or {}), str(datetime.now())))
    conn.commit()
    conn.close()


def clear_triage_state(phone):
    """Reset conversation to idle."""
    set_triage_state(phone, "idle", "", {})


def save_triage_request(request_id, phone, service_type, data):
    """Persist the completed request to the DB."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT OR REPLACE INTO triage_requests
        (request_id, phone, service_type, patient_name, address, complaint,
         preferred_time, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
    """, (
        request_id,
        phone,
        service_type,
        data.get("full_name", ""),
        data.get("address", ""),
        data.get("complaint", ""),
        data.get("preferred_time", "ASAP"),
        str(datetime.now()),
    ))
    conn.commit()
    conn.close()


def mark_request_notified(request_id):
    """Update request status after doctor notification is sent."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        UPDATE triage_requests
        SET status='notified', notified_at=?
        WHERE request_id=?
    """, (str(datetime.now()), request_id))
    conn.commit()
    conn.close()


def generate_request_id():
    """Generate a unique request ID."""
    import random, string
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"TR-{suffix}"


# ── Intent detection ───────────────────────────────────────────────────────────

def detect_intent(body):
    """
    Classify the patient's first message into one of:
      emergency     → life-threatening, redirect to ambulance immediately
      house_call    → wants a doctor at home
      tele_consult  → wants a video/phone consult
      faq_hours     → asking about opening times
      faq_address   → asking about location
      faq_cost      → asking about price
      faq_medical_aid → asking about medical aid
      faq_what_for  → asking what the service is for / if it's suitable
      deflect       → aesthetics, longevity, sports etc — out of scope
      greeting      → hi/hello, unclear intent
      unknown       → can't determine
    """
    b = body.lower().strip()

    # Emergency first — always checked before anything else
    if any(w in b for w in EMERGENCY_KEYWORDS):
        return "emergency"

    # FAQ detection — checked BEFORE service type so "how much does a house call cost?"
    # is treated as a cost question, not a booking request
    cost_words    = ["cost", "price", "fee", "how much", "charge", "rate",
                     "pricing", "koste", "hoeveel"]
    hours_words   = ["hours", "open", "opening hours", "close", "ure", "tyd", "what time do you open"]
    address_words = ["where", "address", "location", "directions", "adres", "find you",
                     "situated", "based"]
    med_aid_words = ["medical aid", "discovery", "momentum", "fedhealth", "bonitas",
                     "medihelp", "insurance", "aid", "scheme", "claim"]
    suitable_words = ["suitable", "right for", "can you help", "do you treat",
                      "can i use", "qualify", "is this for", "should i"]

    if any(w in b for w in med_aid_words):
        return "faq_medical_aid"
    if any(w in b for w in cost_words):
        return "faq_cost"
    if any(w in b for w in hours_words):
        return "faq_hours"
    if any(w in b for w in address_words):
        return "faq_address"
    if any(w in b for w in suitable_words):
        return "faq_what_for"

    # Service type detection — after FAQs
    if any(w in b for w in HOUSE_CALL_KEYWORDS):
        return "house_call"
    if any(w in b for w in TELE_CONSULT_KEYWORDS):
        return "tele_consult"

    # Out-of-scope service deflection
    if any(w in b for w in DEFLECT_KEYWORDS):
        return "deflect"

    # General booking intent (no specific service identified)
    book_words  = ["book", "appointment", "need a doctor", "see a doctor",
                   "consult", "visit", "need help", "sick", "ill", "unwell",
                   "boek", "afspraak", "dokter", "doctor"]
    greet_words = ["hi", "hello", "hey", "good morning", "good afternoon",
                   "good evening", "good night", "howzit", "hallo", "hola",
                   "goeie", "more", "aand"]

    if any(w in b for w in book_words):
        return "book_general"
    if any(w in b for w in greet_words):
        return "greeting"

    return "unknown"


def detect_service_from_body(body):
    """
    When already in a conversation and patient clarifies service type.
    Returns 'house_call', 'tele_consult', or None.
    """
    b = body.lower().strip()
    if any(w in b for w in HOUSE_CALL_KEYWORDS):
        return "house_call"
    if any(w in b for w in TELE_CONSULT_KEYWORDS):
        return "tele_consult"
    # Number shortcuts: "1" = house call, "2" = tele-consult
    if b.strip() in ["1", "house", "home", "callout"]:
        return "house_call"
    if b.strip() in ["2", "tele", "online", "video", "virtual"]:
        return "tele_consult"
    return None


def looks_like_phone(text):
    """Loosely validate a South African phone number."""
    digits = re.sub(r'\D', '', text)
    # SA numbers: 10 digits starting with 0, or 11 digits starting with 27
    return (len(digits) == 10 and digits.startswith('0')) or \
           (len(digits) == 11 and digits.startswith('27')) or \
           (len(digits) >= 9)


def normalise_phone(text):
    """Clean and normalise a phone number string."""
    digits = re.sub(r'\D', '', text)
    if digits.startswith('27') and len(digits) == 11:
        return '0' + digits[2:]
    return digits


# ── Message builders ───────────────────────────────────────────────────────────

def _sign(msg):
    """Append Virtus Health sign-off."""
    return msg + "\n\n— Virtus Health & Medical"


def emergency_response():
    return (
        "⚠️ *This sounds like a medical emergency.*\n\n"
        "Please call an ambulance immediately:\n"
        "📞 *10177* (ER24) or *112* (emergency services)\n\n"
        "The house call service is for urgent but *non-life-threatening* conditions. "
        "Do not wait for a house call if this is an emergency.\n\n"
        "— Virtus Health & Medical"
    )


def deflect_response():
    return _sign(
        "This WhatsApp line handles *house calls* and *tele-consults* only. 😊\n\n"
        "For aesthetics, longevity, sports medicine, and in-practice GP appointments, "
        "please book via our website or give us a call:\n\n"
        f"🌐 *{PRACTICE['website']}*\n"
        f"📞 *{PRACTICE['phone']}*"
    )


def greeting_response():
    return _sign(
        f"👋 Hi! Welcome to *{PRACTICE['name']}*.\n\n"
        "I can help you with a *house call* or *tele-consult* — "
        "both available 24/7.\n\n"
        "Which would you like?\n\n"
        "1️⃣ *House call* — a doctor comes to you (from R2,750)\n"
        "2️⃣ *Tele-consult* — video call with a doctor (R600)\n\n"
        "Or ask me any question about these services."
    )


def triage_question():
    return _sign(
        "Are you looking for a *house call* or a *tele-consult*?\n\n"
        "1️⃣ *House call* — a doctor visits you at home, anywhere in greater Cape Town (from R2,750)\n"
        "2️⃣ *Tele-consult* — a 30-minute video call with a doctor (R600)\n\n"
        "Both are available 24/7."
    )


def faq_then_offer(faq_answer, service=None):
    """Return an FAQ answer followed by a soft prompt to book."""
    if service == "house_call":
        cta = "\n\nWould you like to request a house call? Just say *YES* and I'll get the details."
    elif service == "tele_consult":
        cta = "\n\nWould you like to book a tele-consult? Just say *YES* and I'll get the details."
    else:
        cta = (
            "\n\nCan I help you with a booking?\n"
            "1️⃣ House call  2️⃣ Tele-consult"
        )
    return faq_answer + cta


def collect_prompt(field, service):
    """Return the right question for each data collection step."""
    prompts = {
        "full_name": "What's your full name?",
        "phone": "What's the best number to reach you on?",
        "address": (
            "What's the address you'd like the doctor to come to? "
            "(Please include suburb and city.)"
        ),
        "complaint": (
            "Briefly, what's the medical concern? "
            "(e.g. high fever, severe headache, flu symptoms)"
        ),
        "preferred_time": (
            "When would you like the doctor? "
            "Reply *ASAP* for as soon as possible, or give a preferred time window."
        ),
    }
    return prompts.get(field, f"Please provide your {field.replace('_', ' ')}.")


def confirm_summary(service, data):
    """Build the confirmation summary message."""
    name      = data.get("full_name", "")
    phone     = data.get("phone", "")
    complaint = data.get("complaint", "")
    pref_time = data.get("preferred_time", "ASAP")

    if service == "house_call":
        address = data.get("address", "")
        return _sign(
            f"Please confirm your request:\n\n"
            f"🏠 *House Call*\n"
            f"👤 {name}\n"
            f"📞 {phone}\n"
            f"📍 {address}\n"
            f"🩺 {complaint}\n"
            f"🕐 {pref_time}\n\n"
            f"Reply *YES* to confirm or *NO* to start over."
        )
    else:
        return _sign(
            f"Please confirm your request:\n\n"
            f"💻 *Tele-Consult*\n"
            f"👤 {name}\n"
            f"📞 {phone}\n"
            f"🩺 {complaint}\n"
            f"🕐 {pref_time}\n\n"
            f"Reply *YES* to confirm or *NO* to start over."
        )


# ── Twilio notification sender ─────────────────────────────────────────────────

def send_whatsapp(to_number, message, cfg):
    """
    Send a WhatsApp message via Twilio.
    Returns True on success, False on failure.
    Silently fails if Twilio credentials are not configured.
    """
    try:
        from twilio.rest import Client
        account_sid = cfg.get("twilio", "account_sid", fallback="")
        auth_token  = cfg.get("twilio", "auth_token",  fallback="")
        from_number = cfg.get("twilio", "from_number", fallback="")

        if not account_sid or account_sid.startswith("AC_PLACEHOLDER"):
            print(f"[triage_agent] Twilio not configured — message not sent to {to_number}")
            print(f"[triage_agent] Message preview:\n{message[:200]}")
            return False

        client = Client(account_sid, auth_token)
        client.messages.create(
            from_=from_number,
            to=f"whatsapp:{to_number}" if not to_number.startswith("whatsapp:") else to_number,
            body=message,
        )
        return True

    except Exception as e:
        print(f"[triage_agent] Twilio send error: {e}")
        return False


# ── Collection sequence ────────────────────────────────────────────────────────

HOUSE_CALL_FIELDS  = ["full_name", "phone", "address", "complaint", "preferred_time"]
TELE_CONSULT_FIELDS = ["full_name", "phone", "complaint", "preferred_time"]


def next_missing_field(service, data):
    """Return the next field that still needs to be collected."""
    fields = HOUSE_CALL_FIELDS if service == "house_call" else TELE_CONSULT_FIELDS
    for field in fields:
        if not data.get(field, "").strip():
            return field
    return None  # All fields collected


# ── Main handler ───────────────────────────────────────────────────────────────

def handle_message(phone, body, cfg):
    """
    Main entry point for the triage agent.
    Takes an inbound WhatsApp message, returns a reply string.

    Args:
        phone:  Patient's phone number (with or without 'whatsapp:' prefix)
        body:   Raw message text
        cfg:    ConfigParser object with Twilio and practice settings

    Returns:
        Reply string to send back to the patient.
        Also triggers doctor notification via Twilio when request confirmed.
    """
    init_triage_table()

    state, service, data = get_triage_state(phone)
    body_clean = body.strip()
    b_lower    = body_clean.lower()

    # ── Global escape hatches — work from any state ────────────────────────────

    if b_lower in ["stop", "quit", "exit", "reset", "restart"]:
        clear_triage_state(phone)
        return _sign("No problem — conversation reset. Say *hi* to start again.")

    if b_lower == "help":
        clear_triage_state(phone)
        return _sign(
            f"👋 Here's what I can help with:\n\n"
            f"• *House call* — a doctor visits you at home (from R2,750, 24/7)\n"
            f"• *Tele-consult* — video call with a doctor (R600, 24/7)\n\n"
            f"Just describe what you need, or ask any question.\n\n"
            f"For anything else, call us on {PRACTICE['phone']} "
            f"or visit {PRACTICE['website']}."
        )

    # ── Emergency detection — always checked, any state ────────────────────────

    if detect_intent(body_clean) == "emergency":
        clear_triage_state(phone)
        return emergency_response()

    # ══════════════════════════════════════════════════════════════════════════
    # STATE: IDLE — first message in a new conversation
    # ══════════════════════════════════════════════════════════════════════════

    if state == "idle":
        intent = detect_intent(body_clean)

        if intent == "house_call":
            set_triage_state(phone, "collect", "house_call", {})
            return _sign(
                f"Of course! 🏠 Let's get a doctor to you.\n\n"
                f"A house call starts from *R2,750* and covers greater Cape Town, 24/7.\n\n"
                + collect_prompt("full_name", "house_call")
            )

        if intent == "tele_consult":
            set_triage_state(phone, "collect", "tele_consult", {})
            return _sign(
                f"Sure! 💻 Let's set up your tele-consult.\n\n"
                f"A video call with one of our doctors is *R600*, available 24/7.\n\n"
                + collect_prompt("full_name", "tele_consult")
            )

        if intent == "deflect":
            return deflect_response()

        if intent in ["faq_hours", "faq_address", "faq_cost",
                       "faq_medical_aid", "faq_what_for"]:
            faq_map = {
                "faq_hours":       FAQS["hours"],
                "faq_address":     FAQS["address"],
                "faq_cost":        FAQS["house_call_cost"] + "\n\n" + FAQS["tele_consult_cost"],
                "faq_medical_aid": FAQS["medical_aid"],
                "faq_what_for":    FAQS["house_call_what_included"] + "\n\n" + FAQS["tele_consult_what_for"],
            }
            set_triage_state(phone, "faq", "", {})
            return faq_then_offer(faq_map[intent])

        if intent in ["greeting", "book_general", "unknown"]:
            set_triage_state(phone, "triage", "", {})
            return greeting_response()

    # ══════════════════════════════════════════════════════════════════════════
    # STATE: FAQ — answered a question, waiting to see if they want to book
    # ══════════════════════════════════════════════════════════════════════════

    elif state == "faq":
        # Check if they now want to book
        new_service = detect_service_from_body(body_clean)
        if new_service:
            set_triage_state(phone, "collect", new_service, {})
            intro = "Let's get a doctor to you. 🏠\n\n" if new_service == "house_call" \
                    else "Let's set up your video consult. 💻\n\n"
            return _sign(intro + collect_prompt("full_name", new_service))

        yes_words = ["yes", "ja", "ok", "sure", "please", "book", "proceed", "continue"]
        if any(w in b_lower for w in yes_words):
            set_triage_state(phone, "triage", "", {})
            return triage_question()

        # Another FAQ question
        intent = detect_intent(body_clean)
        if intent in ["faq_hours", "faq_address", "faq_cost",
                       "faq_medical_aid", "faq_what_for"]:
            faq_map = {
                "faq_hours":       FAQS["hours"],
                "faq_address":     FAQS["address"],
                "faq_cost":        FAQS["house_call_cost"] + "\n\n" + FAQS["tele_consult_cost"],
                "faq_medical_aid": FAQS["medical_aid"],
                "faq_what_for":    FAQS["house_call_what_included"] + "\n\n" + FAQS["tele_consult_what_for"],
            }
            return faq_then_offer(faq_map[intent])

        if intent == "deflect":
            return deflect_response()

        # Gentle nudge
        return _sign(
            "Is there anything else I can help you with, "
            "or would you like to request a house call or tele-consult?\n\n"
            "1️⃣ House call  2️⃣ Tele-consult"
        )

    # ══════════════════════════════════════════════════════════════════════════
    # STATE: TRIAGE — greeting sent, waiting for service choice
    # ══════════════════════════════════════════════════════════════════════════

    elif state == "triage":
        new_service = detect_service_from_body(body_clean)
        if new_service:
            set_triage_state(phone, "collect", new_service, {})
            intro = "Great — let's get a doctor to you. 🏠\n\n" if new_service == "house_call" \
                    else "Great — let's set up your video consult. 💻\n\n"
            return _sign(intro + collect_prompt("full_name", new_service))

        # Still not clear — ask one more time simply
        intent = detect_intent(body_clean)
        if intent in ["faq_hours", "faq_address", "faq_cost",
                       "faq_medical_aid", "faq_what_for"]:
            faq_map = {
                "faq_hours":       FAQS["hours"],
                "faq_address":     FAQS["address"],
                "faq_cost":        FAQS["house_call_cost"] + "\n\n" + FAQS["tele_consult_cost"],
                "faq_medical_aid": FAQS["medical_aid"],
                "faq_what_for":    FAQS["house_call_what_included"] + "\n\n" + FAQS["tele_consult_what_for"],
            }
            set_triage_state(phone, "faq", "", {})
            return faq_then_offer(faq_map[intent])

        if intent == "deflect":
            return deflect_response()

        return _sign(
            "Just to confirm — are you looking for:\n\n"
            "1️⃣ *House call* — doctor comes to you\n"
            "2️⃣ *Tele-consult* — video call with a doctor\n\n"
            "Reply with 1 or 2, or describe what you need."
        )

    # ══════════════════════════════════════════════════════════════════════════
    # STATE: COLLECT — gathering patient information one field at a time
    # ══════════════════════════════════════════════════════════════════════════

    elif state == "collect":
        field = next_missing_field(service, data)

        if field is None:
            # All fields collected — move to confirm
            set_triage_state(phone, "confirm", service, data)
            return confirm_summary(service, data)

        # Validate and store the answer to the current field
        answer = body_clean.strip()

        if field == "full_name":
            if len(answer) < 2:
                return _sign("Please enter your full name.")
            data["full_name"] = answer.title()

        elif field == "phone":
            if not looks_like_phone(answer):
                return _sign(
                    "That doesn't look like a valid phone number. "
                    "Please enter your contact number (e.g. 0821234567)."
                )
            data["phone"] = normalise_phone(answer)

        elif field == "address":
            if len(answer) < 5:
                return _sign(
                    "Please provide the full address including street, suburb, and city "
                    "so the doctor knows where to go."
                )
            data["address"] = answer

        elif field == "complaint":
            if len(answer) < 3:
                return _sign(
                    "Could you tell me a bit more about what's wrong? "
                    "A brief description helps the doctor prepare."
                )
            data["complaint"] = answer

        elif field == "preferred_time":
            data["preferred_time"] = answer if answer else "ASAP"

        # Save progress and ask next question
        set_triage_state(phone, "collect", service, data)
        next_field = next_missing_field(service, data)

        if next_field is None:
            # All done — move to confirm
            set_triage_state(phone, "confirm", service, data)
            return confirm_summary(service, data)

        return _sign(collect_prompt(next_field, service))

    # ══════════════════════════════════════════════════════════════════════════
    # STATE: CONFIRM — summary shown, waiting for YES or NO
    # ══════════════════════════════════════════════════════════════════════════

    elif state == "confirm":
        yes_words = ["yes", "ja", "correct", "confirm", "ok", "sure",
                     "book it", "go ahead", "proceed", "send", "please"]
        no_words  = ["no", "nee", "wrong", "cancel", "start over",
                     "restart", "change", "incorrect"]

        if any(w in b_lower for w in yes_words):
            # Generate request ID and save
            request_id = generate_request_id()
            save_triage_request(request_id, phone, service, data)

            # Send doctor notification
            doctor_msg  = build_doctor_notification(service, data)
            doctor_number = cfg.get("practice", "doctor_notify_number", fallback="")

            notified = False
            if doctor_number:
                notified = send_whatsapp(doctor_number, doctor_msg, cfg)
                if notified:
                    mark_request_notified(request_id)

            if not notified:
                # Log to console for manual handling during demo / dev
                print(f"\n[triage_agent] ⚠️  Doctor notification not sent via Twilio.")
                print(f"[triage_agent] Would have sent to: {doctor_number or 'NOT CONFIGURED'}")
                print(f"[triage_agent] Message:\n{doctor_msg}\n")

            # Send patient confirmation
            patient_msg = build_patient_confirmation(service, data)
            clear_triage_state(phone)
            return patient_msg

        elif any(w in b_lower for w in no_words):
            clear_triage_state(phone)
            return _sign(
                "No problem — request cancelled. 👍\n\n"
                "If you'd like to try again, just say *hi* or describe what you need."
            )

        else:
            # Neither yes nor no — re-show summary
            return confirm_summary(service, data)

    # ── Fallback ───────────────────────────────────────────────────────────────

    clear_triage_state(phone)
    return _sign(
        "Sorry, I didn't quite get that. 😊\n\n"
        f"I can help with *house calls* and *tele-consults*.\n"
        f"Or call us on {PRACTICE['phone']}."
    )
