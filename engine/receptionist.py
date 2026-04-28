"""
CadenceWorks — Virtus Health AI Receptionist
=============================================
Handles inbound WhatsApp conversations from patients.
Manages the full booking flow — from greeting to confirmed booking.

Virtus-specific features:
  - Smart doctor routing based on patient need
  - After-hours house call capture (key revenue item)
  - 5-doctor multi-speciality menu
  - Cross-sell awareness

Conversation states per patient:
    idle              → waiting, no active conversation
    booking_need      → understanding what patient needs (for smart routing)
    booking_doc       → showing matched or all doctors
    booking_doc_confirm → confirming smart-suggested doctor
    booking_type      → collecting appointment type
    booking_slot      → offering available slots
    booking_name      → collecting patient name
    booking_confirm   → final confirmation
    house_call_area   → confirming house call coverage area
    house_call_slot   → selecting house call slot
    cancelling        → confirming which booking to cancel

All state is stored in the DB so it survives restarts.
"""

import sqlite3
import configparser
import random
import string
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR    = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "config.ini"
DB_PATH     = BASE_DIR / "virtus_health.db"

# Import Virtus-specific knowledge
from engine.virtus_health_knowledge import (
    PRACTICE, DOCTORS, DEFAULT_DOCTORS, APPOINTMENT_TYPES,
    DOCTOR_ROUTING_RULES, FAQS, SERVICES
)

DAYS_AHEAD = 5


# ── DB helpers ─────────────────────────────────────────────────────────────────

def init_conversation_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            phone        TEXT UNIQUE,
            state        TEXT DEFAULT 'idle',
            data         TEXT DEFAULT '{}',
            updated_at   TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_conversation(phone):
    import json
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute(
        "SELECT state, data FROM conversations WHERE phone=?", (phone,)
    ).fetchone()
    conn.close()
    if row:
        return row[0], json.loads(row[1] or "{}")
    return "idle", {}


def set_conversation(phone, state, data=None):
    import json
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO conversations (phone, state, data, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(phone) DO UPDATE SET
            state=excluded.state,
            data=excluded.data,
            updated_at=excluded.updated_at
    """, (phone, state, json.dumps(data or {}), str(datetime.now())))
    conn.commit()
    conn.close()


def clear_conversation(phone):
    set_conversation(phone, "idle", {})


# ── Slot generator ─────────────────────────────────────────────────────────────

def get_available_slots(doctor_name, count=4, after_hours=False):
    """Return next N available slots for a doctor."""
    doctor = next((d for d in DEFAULT_DOCTORS if d["name"] == doctor_name), DEFAULT_DOCTORS[0])
    slots  = []
    day    = datetime.now()

    if after_hours:
        tomorrow = datetime.now() + timedelta(days=1)
        next_day = datetime.now() + timedelta(days=2)
        if next_day.weekday() >= 5:
            next_day += timedelta(days=2)
        return [
            {
                "date":          tomorrow.strftime("%Y-%m-%d"),
                "display":       tomorrow.strftime("%A %d %B") + " at 07:30 (Early Morning)",
                "time":          "07:30",
                "datetime":      f"{tomorrow.strftime('%Y-%m-%d')} 07:30",
                "is_house_call": True,
            },
            {
                "date":          tomorrow.strftime("%Y-%m-%d"),
                "display":       tomorrow.strftime("%A %d %B") + " at 18:30 (Evening)",
                "time":          "18:30",
                "datetime":      f"{tomorrow.strftime('%Y-%m-%d')} 18:30",
                "is_house_call": True,
            },
            {
                "date":          next_day.strftime("%Y-%m-%d"),
                "display":       next_day.strftime("%A %d %B") + " at 07:30 (Early Morning)",
                "time":          "07:30",
                "datetime":      f"{next_day.strftime('%Y-%m-%d')} 07:30",
                "is_house_call": True,
            },
        ]

    while len(slots) < count:
        day += timedelta(days=1)
        if day.weekday() >= 5:
            continue
        available = doctor["slots"][:]
        random.shuffle(available)
        for time_str in available[:2]:
            slots.append({
                "date":          day.strftime("%Y-%m-%d"),
                "display":       day.strftime("%A %d %B") + f" at {time_str}",
                "time":          time_str,
                "datetime":      f"{day.strftime('%Y-%m-%d')} {time_str}",
                "is_house_call": False,
            })
            if len(slots) >= count:
                break

    return slots[:count]


# ── Smart doctor routing ───────────────────────────────────────────────────────

def suggest_doctor(patient_need_text):
    """Given what the patient described, return best-matched Virtus doctor or None."""
    text = patient_need_text.lower()
    for keyword, doctor_name in DOCTOR_ROUTING_RULES.items():
        if keyword in text:
            return next((d for d in DEFAULT_DOCTORS if d["name"] == doctor_name), None)
    return None


def is_after_hours():
    """Returns True if current time is outside Virtus practice hours.
    Mon-Thu: 08:30-17:30, Fri: 08:30-16:00, Sat: 08:30-12:00, Sun: Closed
    """
    now     = datetime.now()
    hour    = now.hour
    minute  = now.minute
    weekday = now.weekday()
    if weekday == 6:  # Sunday — always closed
        return True
    if weekday == 5:  # Saturday — closes 12:00
        return hour < 8 or (hour == 8 and minute < 30) or hour >= 12
    if weekday == 4:  # Friday — closes 16:00
        return hour < 8 or (hour == 8 and minute < 30) or hour >= 16
    # Mon-Thu — closes 17:30
    return hour < 8 or (hour == 8 and minute < 30) or hour > 17 or (hour == 17 and minute >= 30)


def is_house_call_request(text):
    text = text.lower()
    return any(w in text for w in [
        "house call", "house visit", "home visit", "come to me",
        "come to my", "at my place", "at my home", "my house",
        "come over", "visit me", "home consult",
    ])


# ── Intent detection ───────────────────────────────────────────────────────────

def detect_intent(body):
    b = body.lower().strip()

    book_words      = ["book", "appointment", "schedule", "see a doctor", "consult",
                       "make an appointment", "reserve", "slot", "available"]
    cancel_words    = ["cancel", "cancellation", "cant make", "can't make", "kanselleer"]
    reschedule_words = ["reschedule", "move", "change", "different time", "another time"]
    hours_words     = ["hours", "open", "when", "close", "opening times"]
    address_words   = ["where", "address", "location", "directions", "find you", "parking"]
    greet_words     = ["hi", "hello", "hey", "good morning", "good afternoon",
                       "howzit", "hallo", "goeie", "urgent", "emergency", "help"]
    house_words     = ["house call", "house visit", "home visit", "come to me", "home consult"]
    info_words      = ["iv therapy", "iv drip", "botox", "fillers", "aesthetics",
                       "longevity", "what services", "prices", "cost", "how much",
                       "services", "what do you offer"]

    if any(w in b for w in cancel_words):        return "cancel"
    if any(w in b for w in reschedule_words):    return "reschedule"
    if any(w in b for w in house_words):         return "house_call"
    if any(w in b for w in book_words):          return "book"
    if any(w in b for w in info_words):          return "info"
    if any(w in b for w in hours_words):         return "faq_hours"
    if any(w in b for w in address_words):       return "faq_address"
    if any(w in b for w in greet_words):         return "greeting"
    return "unknown"


def parse_number_choice(body, max_choice):
    b = body.strip()
    try:
        n = int(b)
        if 1 <= n <= max_choice:
            return n - 1
    except ValueError:
        pass
    return None


def generate_booking_id():
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"VH-{suffix}"


# ── FAQ answers ────────────────────────────────────────────────────────────────

def get_faq_answer(intent, cfg=None):
    if intent == "faq_hours":
        return (
            "🕐 *Virtus Health & Medical — Opening Hours:*\n\n"
            "Monday – Thursday: 08:30 – 17:30\n"
            "Friday: 08:30 – 16:00\n"
            "Saturday: 08:30 – 12:00\n"
            "Sunday: Closed\n\n"
            "Sunday: Closed\n\n"
            "📞 After-hours house calls & tele-consults available.\n"
            "Reply *HOUSE CALL* to book an after-hours home visit."
        )
    if intent == "faq_address":
        return (
            "📍 *Virtus Health & Medical*\n\n"
            "3rd Floor, The Point Mall\n"
            "76 Regent Road, Sea Point, Cape Town\n\n"
            "🅿️ Secure basement parking in The Point Mall.\n\n"
            "Reply *BOOK* to schedule an appointment or call +27 21 439 1555."
        )
    if intent == "info":
        return (
            "✨ *Virtus Health Services:*\n\n"
            "🩺 General Practice — GP consults, tele-consults, house calls\n"
            "💉 IV Therapy — hydration, vitamins, antioxidant drips from R1,800\n"
            "✨ Medical Aesthetics — Botox, fillers, mesotherapy with Dr Stefan\n"
            "🌱 Longevity Medicine — biomarker testing, health screening\n"
            "🏃 Sports Medicine — injuries, performance, PRP with Dr Ryan\n"
            "👶 Women's & Children's Health — Dr Jane & Dr Stacey\n\n"
            "Reply *BOOK* to schedule any of these."
        )
    return None


# ── Main conversation handler ──────────────────────────────────────────────────

def handle_message(phone, body, cfg):
    """
    Main entry point. Takes an incoming message, returns a reply string.
    Logs every inbound message and every outbound reply to conversation_log.
    """
    init_conversation_table()
    state, data = get_conversation(phone)

    practice  = "Virtus Health & Medical"
    cancel_n  = "+27 21 439 1555"
    body_clean = body.strip()

    # Log the inbound message immediately
    try:
        from engine import live_sync as _ls
        _ls.init_db()
        _ls.log_message(phone, "inbound", body_clean)
    except Exception:
        pass

    def _send(reply_text, outcome=None, booking_id=None):
        """Log outbound reply and optionally resolve the conversation."""
        try:
            from engine import live_sync as _lsx
            _lsx.log_message(phone, "outbound", reply_text)
            if outcome:
                _lsx.resolve_conversation(phone, outcome, booking_id)
        except Exception:
            pass
        return reply_text

    # ── Global escape hatches ──────────────────────────────────────────────────
    if body_clean.upper() in ["STOP", "CANCEL ALL", "QUIT", "EXIT"]:
        clear_conversation(phone)
        return (
            f"No problem — conversation ended.\n\n"
            f"To start again, say *BOOK* or *HELP*.\n— {practice}"
        )

    if body_clean.upper() == "HELP":
        clear_conversation(phone)
        return (
            f"👋 Hi! Here's what I can help with:\n\n"
            f"• *BOOK* — book an appointment\n"
            f"• *HOUSE CALL* — book an after-hours home visit\n"
            f"• *CANCEL* — cancel an appointment\n"
            f"• *HOURS* — opening times\n"
            f"• *ADDRESS* — find us\n"
            f"• *SERVICES* — what we offer\n\n"
            f"Or call us on {cancel_n}.\n— {practice}"
        )

    if body_clean.upper() == "HOURS":
        return get_faq_answer("faq_hours")
    if body_clean.upper() in ["ADDRESS", "LOCATION"]:
        return get_faq_answer("faq_address")
    if body_clean.upper() in ["SERVICES", "IVINFO"]:
        return get_faq_answer("info")

    # ── State machine ──────────────────────────────────────────────────────────

    # ── IDLE ──────────────────────────────────────────────────────────────────
    if state == "idle":
        intent = detect_intent(body_clean)

        # ── After-hours house call — THE KEY VIRTUS REVENUE CAPTURE ──────────
        if intent == "house_call" or is_house_call_request(body_clean):
            set_conversation(phone, "house_call_area", {})
            fee   = "R3,500" if is_after_hours() else "R2,500"
            label = "after-hours" if is_after_hours() else "standard"
            return (
                f"🏠 *Virtus House Call Booking*\n\n"
                f"Absolutely — we can come to you. "
                f"Our {label} house call fee is *{fee}*.\n\n"
                f"📍 We cover Sea Point, Green Point, Mouille Point, "
                f"Three Anchor Bay, De Waterkant, and the City Bowl.\n\n"
                f"Are you in one of these areas?\n"
                f"Reply *YES* to continue or *NO* to discuss alternatives."
            )

        if intent in ("book", "greeting"):
            set_conversation(phone, "booking_need", {})
            if intent == "greeting":
                return (
                    f"Hi there! 👋 Welcome to *{practice}*.\n\n"
                    f"What brings you in today? "
                    f"Tell me briefly what you need and I'll match you with the right doctor.\n\n"
                    f"_(e.g. 'GP consult', 'Botox', 'IV drip', 'sports injury', "
                    f"'smear test', 'children', 'longevity')_"
                )
            else:
                return (
                    f"Let's get you booked in! 👍\n\n"
                    f"What do you need? I'll match you with the right doctor.\n\n"
                    f"_(e.g. 'GP consult', 'Botox', 'IV drip', 'sports injury', "
                    f"'smear test', 'children', 'longevity')_"
                )

        elif intent == "cancel":
            booking = lookup_booking_by_phone(phone)
            if booking:
                data = {
                    "appointment_id": booking["appointment_id"],
                    "appt_display":   booking["appt_display"],
                }
                set_conversation(phone, "cancelling", data)
                return (
                    f"I found your upcoming appointment:\n\n"
                    f"📅 {booking['appt_display']}\n"
                    f"👨‍⚕️ {booking['provider']}\n\n"
                    f"Are you sure you want to cancel?\n"
                    f"Reply *YES* to confirm or *NO* to keep it."
                )
            else:
                clear_conversation(phone)
                return (
                    f"I couldn't find an upcoming booking for your number.\n\n"
                    f"To cancel, please call us on {cancel_n}.\n— {practice}"
                )

        elif intent == "reschedule":
            clear_conversation(phone)
            return (
                f"To reschedule, please call or WhatsApp us on {cancel_n} "
                f"and we'll find you a new time. 🙏\n— {practice}"
            )

        elif intent in ("faq_hours", "faq_address", "info"):
            return get_faq_answer(intent)

        else:
            set_conversation(phone, "idle", {})
            return (
                f"Hi! 👋 Thanks for reaching out.\n\n"
                f"I can help with:\n"
                f"• *BOOK* — book an appointment\n"
                f"• *HOUSE CALL* — after-hours home visit\n"
                f"• *CANCEL* — cancel an appointment\n"
                f"• *SERVICES* — what we offer\n"
                f"• *HOURS* — opening times\n\n"
                f"Or call us on {cancel_n}.\n— {practice}"
            )

    # ── HOUSE CALL: confirm area ──────────────────────────────────────────────
    elif state == "house_call_area":
        if body_clean.upper() in ["YES", "JA", "YEP", "Y"]:
            data["is_house_call"] = True
            slots = get_available_slots("Dr Ryan Jankelowitz", count=3, after_hours=True)
            data["slots"]  = slots
            data["doctor"] = "Dr Ryan Jankelowitz"
            data["appointment_type"] = "After-Hours House Call" if is_after_hours() else "House Call"
            data["fee"] = 3500 if is_after_hours() else 2500
            slot_list = "\n".join(f"{i+1}. {s['display']}" for i, s in enumerate(slots))
            set_conversation(phone, "house_call_slot", data)
            return (
                f"Available house call slots:\n\n"
                f"{slot_list}\n\n"
                f"Reply with a number to select your preferred time."
            )
        elif body_clean.upper() in ["NO", "NAH", "N"]:
            clear_conversation(phone)
            return (
                f"Please call us on {cancel_n} and we'll do our best to arrange "
                f"something for you. 🙏\n— {practice}"
            )
        else:
            # Try to treat as an address
            data["is_house_call"] = True
            data["address"] = body_clean
            slots = get_available_slots("Dr Ryan Jankelowitz", count=3, after_hours=True)
            data["slots"]  = slots
            data["doctor"] = "Dr Ryan Jankelowitz"
            data["appointment_type"] = "After-Hours House Call" if is_after_hours() else "House Call"
            data["fee"] = 3500 if is_after_hours() else 2500
            slot_list = "\n".join(f"{i+1}. {s['display']}" for i, s in enumerate(slots))
            set_conversation(phone, "house_call_slot", data)
            return (
                f"Got it! Available house call slots:\n\n"
                f"{slot_list}\n\n"
                f"Reply with a number to select."
            )

    # ── HOUSE CALL: select slot ───────────────────────────────────────────────
    elif state == "house_call_slot":
        slots = data.get("slots", [])
        choice = parse_number_choice(body_clean, len(slots))
        if choice is None:
            slot_list = "\n".join(f"{i+1}. {s['display']}" for i, s in enumerate(slots))
            return f"Please reply with a number:\n\n{slot_list}"
        data["slot"] = slots[choice]
        set_conversation(phone, "booking_name", data)
        return (
            f"Almost done! 🎉\n\n"
            f"What is your full name and address?\n"
            f"_(e.g. Sarah Smith, 14 Beach Road, Sea Point)_"
        )

    # ── BOOKING: Understand patient need (smart routing) ──────────────────────
    elif state == "booking_need":
        suggested = suggest_doctor(body_clean)
        data["patient_need"] = body_clean

        if suggested:
            data["suggested_doctor"] = suggested["name"]
            set_conversation(phone, "booking_doc_confirm", data)
            # Find what specialist this doctor is
            doc_obj = next((d for d in DOCTORS if d["name"] == suggested["name"]), None)
            specialty = ", ".join(doc_obj["interests"][:2]) if doc_obj else "General Practice"
            return (
                f"Based on what you've described, I'd recommend:\n\n"
                f"👨‍⚕️ *{suggested['name']}*\n"
                f"🏥 {specialty}\n\n"
                f"Reply *YES* to book with them, or *NO* to see all our doctors."
            )
        else:
            doctor_list = "\n".join(
                f"{i+1}. {d['name']} — {', '.join(DOCTORS[i]['interests'][:2])}"
                for i, d in enumerate(DEFAULT_DOCTORS)
            )
            set_conversation(phone, "booking_doc", data)
            return (
                f"Our Virtus team:\n\n{doctor_list}\n\n"
                f"Who would you like to see? Reply with a number."
            )

    # ── BOOKING: Confirm smart-suggested doctor ────────────────────────────────
    elif state == "booking_doc_confirm":
        if body_clean.upper() in ["YES", "JA", "Y", "YEP"]:
            data["doctor"] = data.get("suggested_doctor")
            # Build appointment type list
            type_list = "\n".join(f"{i+1}. {t}" for i, t in enumerate(APPOINTMENT_TYPES[:20]))
            set_conversation(phone, "booking_type", data)
            return (
                f"Great — *{data['doctor']}* it is! 👍\n\n"
                f"What type of appointment?\n\n{type_list}\n\n"
                f"Reply with a number."
            )
        else:
            doctor_list = "\n".join(
                f"{i+1}. {d['name']} — {', '.join(DOCTORS[i]['interests'][:2])}"
                for i, d in enumerate(DEFAULT_DOCTORS)
            )
            set_conversation(phone, "booking_doc", data)
            return f"Our Virtus team:\n\n{doctor_list}\n\nReply with a number."

    # ── BOOKING: Choose doctor from full list ─────────────────────────────────
    elif state == "booking_doc":
        choice = parse_number_choice(body_clean, len(DEFAULT_DOCTORS))
        if choice is None:
            for i, d in enumerate(DEFAULT_DOCTORS):
                if d["name"].lower() in body_clean.lower():
                    choice = i
                    break
        if choice is None:
            doctor_list = "\n".join(
                f"{i+1}. {d['name']}" for i, d in enumerate(DEFAULT_DOCTORS)
            )
            return f"Please reply with a number:\n\n{doctor_list}"

        doctor = DEFAULT_DOCTORS[choice]
        data["doctor"] = doctor["name"]
        type_list = "\n".join(f"{i+1}. {t}" for i, t in enumerate(APPOINTMENT_TYPES[:20]))
        set_conversation(phone, "booking_type", data)
        return (
            f"Great — *{doctor['name']}* it is! 👍\n\n"
            f"What type of appointment?\n\n{type_list}\n\nReply with a number."
        )

    # ── BOOKING: Choose appointment type ──────────────────────────────────────
    elif state == "booking_type":
        choice = parse_number_choice(body_clean, len(APPOINTMENT_TYPES))
        if choice is None:
            for i, t in enumerate(APPOINTMENT_TYPES):
                if t.lower() in body_clean.lower():
                    choice = i
                    break
        if choice is None:
            type_list = "\n".join(f"{i+1}. {t}" for i, t in enumerate(APPOINTMENT_TYPES[:20]))
            return f"Please reply with a number:\n\n{type_list}"

        data["appointment_type"] = APPOINTMENT_TYPES[choice]
        slots     = get_available_slots(data["doctor"])
        data["slots"] = slots
        slot_list = "\n".join(f"{i+1}. {s['display']}" for i, s in enumerate(slots))
        set_conversation(phone, "booking_slot", data)
        return (
            f"Available slots with *{data['doctor']}*:\n\n"
            f"{slot_list}\n\n"
            f"Reply with a number, or say *OTHER* if none work."
        )

    # ── BOOKING: Choose slot ───────────────────────────────────────────────────
    elif state == "booking_slot":
        slots = data.get("slots", [])

        if body_clean.upper() == "OTHER":
            clear_conversation(phone)
            return (
                f"No problem — call us on {cancel_n} and we'll find a time that works. 🙏"
                f"\n— {practice}"
            )

        choice = parse_number_choice(body_clean, len(slots))
        if choice is None:
            slot_list = "\n".join(f"{i+1}. {s['display']}" for i, s in enumerate(slots))
            return f"Please reply with a number:\n\n{slot_list}\n\nOr say *OTHER* for more options."

        data["slot"] = slots[choice]
        set_conversation(phone, "booking_name", data)
        return "Almost done! 🎉\n\nWhat is your full name?"

    # ── BOOKING: Collect name (and address for house calls) ───────────────────
    elif state == "booking_name":
        name_input = body_clean.strip()
        # Parse "Name, Address" format for house calls
        if data.get("is_house_call") and "," in name_input:
            parts = name_input.split(",", 1)
            data["patient_name"] = parts[0].strip().title()
            data["address"]      = parts[1].strip()
        else:
            data["patient_name"] = name_input.title()

        if len(data["patient_name"]) < 2:
            return "Please enter your full name."

        slot      = data.get("slot", {})
        doctor    = data.get("doctor", "")
        appt_type = data.get("appointment_type", "")

        set_conversation(phone, "booking_confirm", data)
        address_line = (
            f"\n🏠 *Address:* {data.get('address', 'We will confirm this with you')}"
            if data.get("is_house_call") else
            f"\n📍 3rd Floor, The Point Mall, Sea Point"
        )
        return (
            f"Here's your booking summary:\n\n"
            f"👤 *{data['patient_name']}*\n"
            f"👨‍⚕️ *{doctor}*\n"
            f"📋 *{appt_type}*\n"
            f"📅 *{slot.get('display', '')}*"
            f"{address_line}\n\n"
            f"Reply *CONFIRM* to book or *CANCEL* to start over."
        )

    # ── BOOKING: Final confirmation ────────────────────────────────────────────
    elif state == "booking_confirm":
        if body_clean.upper() in ["CONFIRM", "YES", "JA", "OK", "BOOK"]:
            slot      = data.get("slot", {})
            name      = data.get("patient_name", "Patient")
            doctor    = data.get("doctor", "Dr Ryan Jankelowitz")
            appt_type = data.get("appointment_type", "GP Consultation")
            appt_id   = generate_booking_id()
            is_house_call = data.get("is_house_call", False)

            # Look up fee
            fee = data.get("fee", 750)
            if not fee:
                for pillar_data in SERVICES.values():
                    for svc in pillar_data["services"]:
                        if svc["name"] == appt_type:
                            fee = svc["fee"]
                            break

            clean_phone = phone.replace("whatsapp:", "").replace("+27", "0")

            try:
                from engine import live_sync
                live_sync.init_db()
                live_sync.add_manual_booking({
                    "appointment_id":   appt_id,
                    "patient_name":     name,
                    "phone":            clean_phone,
                    "appt_datetime":    slot.get("datetime", ""),
                    "provider":         doctor,
                    "patient_type":     "New",
                    "appointment_type": appt_type,
                    "fee":              fee,
                    "channel":          "WhatsApp Agent",
                    "source":           "WhatsApp Agent",
                })
                # Resolve the conversation as booking_made
                try:
                    live_sync.resolve_conversation(phone, "booking_made", appt_id)
                except Exception:
                    pass
                booking_created = True
            except Exception as e:
                print(f"[receptionist] booking error: {e}")
                booking_created = False

            clear_conversation(phone)

            if booking_created:
                if is_house_call:
                    location_line = (
                        f"🏠 We'll come to: *{data.get('address', 'your address')}*\n"
                        f"Our doctor will call you 30 minutes before arriving."
                    )
                else:
                    location_line = "📍 *Virtus Health*, 3rd Floor, The Point Mall, Sea Point"

                return (
                    f"✅ *Booking Confirmed!*\n\n"
                    f"👤 {name}\n"
                    f"👨‍⚕️ {doctor}\n"
                    f"📋 {appt_type}\n"
                    f"📅 {slot.get('display', '')}\n"
                    f"{location_line}\n\n"
                    f"We'll send you a reminder before your appointment. "
                    f"To cancel, reply *CANCEL* or call {cancel_n}.\n\n"
                    f"See you soon! 🙏\n— {practice}"
                )
            else:
                return (
                    f"Something went wrong on our end. 😔\n\n"
                    f"Please call us on {cancel_n} to confirm your booking.\n— {practice}"
                )

        elif body_clean.upper() in ["CANCEL", "NO", "START OVER"]:
            try:
                from engine import live_sync as _lsx
                _lsx.resolve_conversation(phone, "no_booking")
            except Exception:
                pass
            clear_conversation(phone)
            return (
                f"No problem — booking cancelled. 👍\n\n"
                f"To start again, say *BOOK*.\n— {practice}"
            )
        else:
            return "Please reply *CONFIRM* to book or *CANCEL* to start over."

    # ── CANCELLATION ──────────────────────────────────────────────────────────
    elif state == "cancelling":
        if body_clean.upper() in ["YES", "JA", "CONFIRM", "CANCEL"]:
            appt_id = data.get("appointment_id", "")
            if appt_id:
                try:
                    from engine import live_sync
                    live_sync.update_booking_status(appt_id, "Cancelled")
                except Exception:
                    pass
            clear_conversation(phone)
            return (
                f"✅ Your appointment has been cancelled.\n\n"
                f"To rebook, say *BOOK* or call {cancel_n}.\n— {practice}"
            )
        elif body_clean.upper() in ["NO", "KEEP"]:
            clear_conversation(phone)
            return (
                f"No problem — your appointment is still on. 👍\n\n"
                f"See you then! 🙏\n— {practice}"
            )
        else:
            return "Reply *YES* to confirm the cancellation or *NO* to keep your appointment."

    # ── Fallback ───────────────────────────────────────────────────────────────
    clear_conversation(phone)
    return (
        f"Sorry, I didn't quite catch that. 😊\n\n"
        f"Reply *HELP* to see what I can do, or call {cancel_n}.\n— {practice}"
    )


# ── Booking lookup helper ──────────────────────────────────────────────────────

def lookup_booking_by_phone(phone):
    """Find the next upcoming booking for this phone number."""
    clean = phone.replace("whatsapp:", "").replace("+27", "0").replace("+", "")
    conn  = sqlite3.connect(DB_PATH)
    row   = conn.execute("""
        SELECT appointment_id, patient_name, appt_datetime, provider
        FROM bookings
        WHERE (phone LIKE ? OR phone LIKE ?)
          AND status = 'Pending'
        ORDER BY appt_datetime ASC
        LIMIT 1
    """, (f"%{clean[-9:]}", f"%{clean}")).fetchone()
    conn.close()

    if row:
        try:
            dt = datetime.fromisoformat(str(row[2]))
            display = dt.strftime("%A %d %B at %H:%M")
        except Exception:
            display = str(row[2])
        return {
            "appointment_id": row[0],
            "patient_name":   row[1],
            "appt_display":   display,
            "provider":       row[3],
        }
    return None
