"""
CadenceWorks — Virtus Health & Medical Triage Agent (LLM Version)
========================================================
Replaces the keyword state machine with Claude (claude-haiku-4-5)
for natural, conversational WhatsApp handling.

How it works:
  1. Patient message arrives via webhook
  2. Emergency check runs first (pure Python, no API cost)
  3. Conversation history loaded from SQLite
  4. Full history + system prompt sent to Claude API
  5. Claude responds naturally and embeds a hidden JSON block
     when all booking fields are collected
  6. Python extracts the JSON, triggers doctor notification,
     strips JSON from the reply before sending to patient

Drop-in replacement for triage_agent.py.
Switch in webhook_server.py: import triage_agent_llm as triage_agent
"""

import sqlite3
import json
import re
import urllib.request
import urllib.error
import random
import string
from datetime import datetime
from pathlib import Path

from engine.virtus_health_knowledge import (
    PRACTICE,
    EMERGENCY_KEYWORDS,
    build_system_prompt,
    build_doctor_notification,
    build_patient_confirmation,
)

BASE_DIR = Path(__file__).parent.parent
DB_PATH  = BASE_DIR / "virtus_health.db"

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL             = "claude-haiku-4-5-20251001"
MAX_TOKENS        = 600
MAX_HISTORY       = 20  # Max messages to keep in context per conversation


# ── DB helpers ─────────────────────────────────────────────────────────────────

def init_triage_table():
    """Create all required tables."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_conversations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            phone      TEXT UNIQUE,
            history    TEXT DEFAULT '[]',
            status     TEXT DEFAULT 'active',
            updated_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS triage_requests (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id     TEXT UNIQUE,
            phone          TEXT,
            service_type   TEXT,
            patient_name   TEXT,
            address        TEXT,
            complaint      TEXT,
            preferred_time TEXT,
            status         TEXT DEFAULT 'pending',
            created_at     TEXT,
            notified_at    TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_history(phone):
    """Load conversation history for a phone number."""
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute(
        "SELECT history FROM llm_conversations WHERE phone=?", (phone,)
    ).fetchone()
    conn.close()
    if row:
        return json.loads(row[0] or "[]")
    return []


def save_history(phone, history):
    """Persist conversation history, trimming to MAX_HISTORY messages."""
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO llm_conversations (phone, history, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(phone) DO UPDATE SET
            history=excluded.history,
            updated_at=excluded.updated_at
    """, (phone, json.dumps(history), str(datetime.now())))
    conn.commit()
    conn.close()


def clear_history(phone):
    """Reset conversation."""
    save_history(phone, [])


def save_triage_request(request_id, phone, service_type, data):
    """Persist completed booking request."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT OR REPLACE INTO triage_requests
        (request_id, phone, service_type, patient_name, address,
         complaint, preferred_time, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
    """, (
        request_id, phone, service_type,
        data.get("full_name", ""),
        data.get("address", ""),
        data.get("complaint", ""),
        data.get("preferred_time", "ASAP"),
        str(datetime.now()),
    ))
    conn.commit()
    conn.close()


def mark_request_notified(request_id):
    """Mark a request as notified."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        UPDATE triage_requests SET status='notified', notified_at=?
        WHERE request_id=?
    """, (str(datetime.now()), request_id))
    conn.commit()
    conn.close()


def generate_request_id():
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"TR-{suffix}"


# ── Emergency detection ────────────────────────────────────────────────────────
# Runs before the API call — fast, free, and catches the critical cases.

def is_emergency(body):
    b = body.lower()
    return any(w in b for w in EMERGENCY_KEYWORDS)


def emergency_response():
    return (
        "⚠️ *This sounds like a medical emergency.*\n\n"
        "Please call an ambulance immediately:\n"
        "📞 *10177* (ER24) or *112* (emergency services)\n\n"
        "The house call service is for urgent but *non-life-threatening* "
        "conditions. Do not wait for a house call in an emergency.\n\n"
        "— Virtus Health & Medical"
    )


# ── System prompt ──────────────────────────────────────────────────────────────

def get_system_prompt():
    """
    Build the full system prompt for Claude.
    Extends the base knowledge prompt with LLM-specific instructions
    for JSON output and conversation style.
    Injects current SA date and time so Claude can resolve relative
    time references like "tonight", "tomorrow", "ASAP" into real values.
    """
    from datetime import datetime, timezone, timedelta
    # SAST = UTC+2 (no daylight saving in South Africa)
    sa_tz  = timezone(timedelta(hours=2))
    now_sa = datetime.now(sa_tz)

    day_name  = now_sa.strftime("%A")          # e.g. Wednesday
    date_str  = now_sa.strftime("%d %B %Y")    # e.g. 01 April 2026
    time_str  = now_sa.strftime("%H:%M")       # e.g. 14:35
    datetime_context = (
        f"CURRENT DATE AND TIME (South Africa, SAST):\n"
        f"  Day:  {day_name}\n"
        f"  Date: {date_str}\n"
        f"  Time: {time_str}\n\n"
        f"Use this to resolve relative time references:\n"
        f"  - 'ASAP' or 'now'     → today {date_str}, as soon as possible\n"
        f"  - 'tonight'           → today {date_str} evening (after 17:00)\n"
        f"  - 'tomorrow morning'  → {(now_sa + timedelta(days=1)).strftime('%d %B %Y')} morning\n"
        f"  - 'tomorrow'          → {(now_sa + timedelta(days=1)).strftime('%d %B %Y')}\n"
        f"When collecting preferred_time, always resolve it to a specific date and "
        f"time window (e.g. '01 April 2026, evening' or '02 April 2026, 09:00–11:00') "
        f"before confirming the booking. Never leave it as just 'ASAP' or 'tonight' "
        f"in the booking JSON — always include the actual date.\n"
    )

    base = datetime_context + build_system_prompt()

    llm_instructions = """

═══════════════════════════════════════
RESPONSE FORMAT — CRITICAL
═══════════════════════════════════════
You are having a natural WhatsApp conversation. Be warm, concise, and human.
Do NOT use formal numbered lists unless offering a simple 1/2 choice.
Do NOT repeat the patient's information back unnecessarily.
Do NOT use overly formal language — this is WhatsApp, not an email.

SHORT MESSAGES: Keep responses under 150 words. WhatsApp messages should
feel like texts, not paragraphs. If you have a lot to say, say the most
important part and let the patient respond.

COLLECT INFORMATION NATURALLY: Don't ask all questions at once. Ask one
thing at a time. If the patient has already volunteered information in their
message (e.g. "I'm in Sea Point with a fever"), acknowledge it and only ask
for what's still missing.

EXTRACT WHAT'S ALREADY THERE: If a patient says "I'm Sipho, I need a doctor
at 14 Beach Road Sea Point, I have a bad flu", extract all three pieces — don't ask
for things they've already told you.

═══════════════════════════════════════
BOOKING COMPLETION — JSON TRIGGER
═══════════════════════════════════════
Once you have confirmed ALL required fields AND the patient has said YES to
your summary, append this JSON block at the very end of your message.
The JSON will be stripped out before sending to the patient — it is only
for the system to process.

Required fields for HOUSE CALL:
  full_name, phone, address, complaint, preferred_time

Required fields for TELE-CONSULT:
  full_name, phone, complaint, preferred_time

When all fields are confirmed, end your message with:

%%BOOKING_COMPLETE%%
{
  "service_type": "house_call",
  "full_name": "Patient Name",
  "phone": "0821234567",
  "address": "14 Beach Road, Sea Point, Cape Town",
  "complaint": "High fever, headache",
  "preferred_time": "ASAP"
}
%%END%%

Use "tele_consult" for tele-consult bookings.
Only output this block AFTER the patient has confirmed YES to your summary.
Never output this block speculatively or before confirmation.

═══════════════════════════════════════
CONVERSATION EXAMPLES
═══════════════════════════════════════

GOOD (natural):
Patient: "hi im not feeling well fever and headache can someone come"
Agent: "Hi! Sorry to hear that. Let's get a doctor to you — sounds like a
house call would help. Can I get your name and address?"

BAD (robotic):
Agent: "Are you looking for a house call or tele-consult? Reply 1 or 2."

GOOD (extracting info already given):
Patient: "I'm James, 082 555 1234, at 5 Ocean View Drive Camps Bay, I have
food poisoning, need someone asap"
Agent: "Hi James! Got all your details. Just to confirm — house call to
5 Ocean View Drive, Camps Bay for food poisoning, as soon as possible?
Reply YES and I'll get a doctor to you."

GOOD (short FAQ answer):
Patient: "do you take medical aid"
Agent: "We're private — no direct billing. We give you a detailed invoice
to claim back from your medical aid. Anything else I can help with?"
"""
    return base + llm_instructions


# ── Claude API call ────────────────────────────────────────────────────────────

def call_claude(history, cfg):
    """
    Send conversation history to Claude and get a response.
    Uses urllib (no requests library needed).

    Returns the response text or an error fallback string.
    """
    api_key = cfg.get("anthropic", "api_key", fallback="")

    if not api_key or api_key == "YOUR_API_KEY_HERE":
        print("[triage_agent_llm] Anthropic API key not configured in config.ini")
        return (
            f"Sorry, I'm having a technical issue. Please call us on "
            f"{PRACTICE['phone']} and we'll help you directly.\n\n— Virtus Health & Medical"
        )

    payload = json.dumps({
        "model":      MODEL,
        "max_tokens": MAX_TOKENS,
        "system":     get_system_prompt(),
        "messages":   history,
    }).encode("utf-8")

    req = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=payload,
        headers={
            "Content-Type":      "application/json",
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return result["content"][0]["text"]

    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"[triage_agent_llm] API error {e.code}: {error_body}")
        return (
            f"Sorry, something went wrong. Please call us on "
            f"{PRACTICE['phone']}.\n\n— Virtus Health & Medical"
        )
    except Exception as ex:
        print(f"[triage_agent_llm] Unexpected error: {ex}")
        return (
            f"Sorry, something went wrong. Please call us on "
            f"{PRACTICE['phone']}.\n\n— Virtus Health & Medical"
        )


# ── Booking completion detector ────────────────────────────────────────────────

def extract_booking(response_text):
    """
    Look for the %%BOOKING_COMPLETE%% ... %%END%% block in Claude's response.
    Returns (clean_text, booking_data) where booking_data is None if not present.
    """
    pattern = r'%%BOOKING_COMPLETE%%\s*(.*?)\s*%%END%%'
    match   = re.search(pattern, response_text, re.DOTALL)

    if not match:
        return response_text.strip(), None

    # Strip the JSON block from the text sent to patient
    clean_text = re.sub(pattern, '', response_text, flags=re.DOTALL).strip()

    try:
        booking_data = json.loads(match.group(1).strip())
        return clean_text, booking_data
    except json.JSONDecodeError as e:
        print(f"[triage_agent_llm] JSON parse error in booking block: {e}")
        print(f"[triage_agent_llm] Raw block: {match.group(1)}")
        return clean_text, None


# ── Twilio sender ──────────────────────────────────────────────────────────────

def send_whatsapp(to_number, message, cfg):
    """Send a WhatsApp message via Twilio."""
    try:
        from twilio.rest import Client
        account_sid = cfg.get("twilio", "account_sid", fallback="")
        auth_token  = cfg.get("twilio", "auth_token",  fallback="")
        from_number = cfg.get("twilio", "from_number", fallback="")

        if not account_sid or account_sid.startswith("AC_PLACEHOLDER"):
            print(f"[triage_agent_llm] Twilio not configured — not sending to {to_number}")
            print(f"[triage_agent_llm] Message:\n{message}")
            return False

        client = Client(account_sid, auth_token)
        client.messages.create(
            from_=from_number,
            to=f"whatsapp:{to_number}" if not to_number.startswith("whatsapp:") else to_number,
            body=message,
        )
        return True

    except Exception as e:
        print(f"[triage_agent_llm] Twilio error: {e}")
        return False


# ── Main handler ───────────────────────────────────────────────────────────────

def handle_message(phone, body, cfg):
    """
    Main entry point. Receives a WhatsApp message, returns a reply.

    Args:
        phone: Patient phone number (with or without 'whatsapp:' prefix)
        body:  Raw message text from patient
        cfg:   ConfigParser with Twilio + Anthropic + practice settings

    Returns:
        Reply string to send back to the patient via Twilio.
    """
    init_triage_table()
    body_clean = body.strip()

    # ── Hard reset ─────────────────────────────────────────────────────────────
    if body_clean.lower() in ["stop", "reset", "restart", "quit"]:
        clear_history(phone)
        return (
            f"Conversation reset. Say hi whenever you're ready.\n\n"
            f"— Virtus Health & Medical"
        )

    # ── Emergency — fast Python check, no API cost ─────────────────────────────
    if is_emergency(body_clean):
        clear_history(phone)
        return emergency_response()

    # ── Load history and append new patient message ────────────────────────────
    history = get_history(phone)
    history.append({"role": "user", "content": body_clean})

    # ── Call Claude ────────────────────────────────────────────────────────────
    print(f"[triage_agent_llm] Calling Claude for {phone} — {len(history)} messages in history")
    raw_response = call_claude(history, cfg)

    # ── Check for completed booking ────────────────────────────────────────────
    reply, booking_data = extract_booking(raw_response)

    if booking_data:
        service_type = booking_data.get("service_type", "house_call")
        request_id   = generate_request_id()

        # Save request to DB
        save_triage_request(request_id, phone, service_type, booking_data)

        # Send doctor notification
        doctor_number = cfg.get("practice", "doctor_notify_number", fallback="")
        notified = False

        if doctor_number:
            doctor_msg = build_doctor_notification(service_type, booking_data)
            notified   = send_whatsapp(doctor_number, doctor_msg, cfg)
            if notified:
                mark_request_notified(request_id)
                print(f"[triage_agent_llm] Doctor notified — request {request_id}")
            else:
                print(f"[triage_agent_llm] Doctor notification failed — request {request_id}")
                print(f"[triage_agent_llm] Doctor message:\n{doctor_msg}")
        else:
            print(f"[triage_agent_llm] No doctor_notify_number configured")

        # Override reply with the patient confirmation message
        reply = build_patient_confirmation(service_type, booking_data)

        # Clear history — conversation complete
        clear_history(phone)

    else:
        # Ongoing conversation — save updated history with assistant reply
        history.append({"role": "assistant", "content": reply})
        save_history(phone, history)

    return reply
