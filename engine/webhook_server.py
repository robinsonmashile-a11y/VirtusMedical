"""
CadenceWorks — Twilio Webhook Server
=====================================
Receives incoming WhatsApp messages from patients via Twilio.

Routing:
  - All inbound messages → triage_agent (Virtus Health house call / tele-consult flow)
  - Legacy receptionist kept for dashboard-initiated booking flows

Usage:
    python3 engine/webhook_server.py

Then expose with ngrok:
    ngrok http 5005

Set Twilio webhook URL in Twilio Console to:
    https://<ngrok-url>/whatsapp/incoming

For Virtus Health, the practice WhatsApp number (+27 21 439 1555) should
point to this webhook. All inbound messages are handled by the triage agent.
"""

import os
import urllib.parse
import urllib.request
import urllib.error
import base64
import json
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE_DIR = Path(__file__).parent.parent
PORT     = int(os.environ.get("PORT", 5005))


def load_config():
    from engine.config_helper import load_config as _load
    return _load()


def send_whatsapp(to_number, message, cfg):
    sid      = cfg.get("twilio", "account_sid")
    token    = cfg.get("twilio", "auth_token")
    from_num = cfg.get("twilio", "from_number", fallback="whatsapp:+14155238886")

    if not to_number.startswith("whatsapp:"):
        to_number = f"whatsapp:{to_number}"

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
            return {"success": True, "sid": result.get("sid")}
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return {"success": False, "error": f"HTTP {e.code}: {body}"}
    except Exception as ex:
        return {"success": False, "error": str(ex)}


def save_to_inbox(from_number, body, intent, patient_name=""):
    import sqlite3
    DB_PATH = BASE_DIR / "virtus_health.db"
    status  = "resolved" if intent in ("confirmed", "cancelled") else "needs_attention"
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS inbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_number TEXT, patient_name TEXT, appointment_id TEXT,
                body TEXT, intent TEXT, status TEXT, auto_replied INTEGER DEFAULT 1, ts TEXT
            )
        """)
        conn.execute("""
            INSERT INTO inbox (from_number, patient_name, appointment_id, body, intent, status, ts)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (from_number, patient_name, "", body, intent, status, str(datetime.now())))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"  [inbox error] {e}")


class TwilioWebhookHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        if self.path != "/whatsapp/incoming":
            self.send_response(404)
            self.end_headers()
            return

        length      = int(self.headers.get("Content-Length", 0))
        raw         = self.rfile.read(length).decode()
        params      = dict(urllib.parse.parse_qsl(raw))
        from_number = params.get("From", "")
        body        = params.get("Body", "").strip()
        num_media   = int(params.get("NumMedia", "0") or "0")

        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] <- {from_number}: {body!r}")

        cfg   = load_config()
        reply = ""

        # ── Handle voice notes and media ───────────────────────────────────────
        if num_media > 0 and not body:
            media_type = params.get("MediaContentType0", "")
            if "audio" in media_type:
                reply = (
                    "Hi! I received a voice note but I can only read text messages. "
                    "Please type your message and I'll help you right away. 😊\n\n— Virtus Health & Medical"
                )
            else:
                reply = (
                    "I received a file but can only read text. "
                    "Please type what you need and I'll help you. 😊\n\n— Virtus Health & Medical"
                )
            send_whatsapp(from_number, reply, cfg)
            save_to_inbox(from_number, "[media]", "media")
            self.send_response(200)
            self.send_header("Content-Type", "text/xml")
            self.end_headers()
            self.wfile.write(b"<?xml version='1.0' encoding='UTF-8'?><Response></Response>")
            return

        # ── Skip empty messages ────────────────────────────────────────────────
        if not body:
            print(f"  [skipped] Empty body from {from_number}")
            self.send_response(200)
            self.send_header("Content-Type", "text/xml")
            self.end_headers()
            self.wfile.write(b"<?xml version='1.0' encoding='UTF-8'?><Response></Response>")
            return

        # ── Route to Virtus WhatsApp Booking Agent (receptionist) ─────────────
        try:
            import sys
            sys.path.insert(0, str(BASE_DIR))
            from engine import receptionist as booking_agent
            from engine import live_sync as ls
            booking_agent.init_conversation_table()
            ls.init_db()
            reply = booking_agent.handle_message(from_number, body, cfg)
        except Exception as e:
            import traceback
            print(f"  [booking_agent error] {e}")
            traceback.print_exc()
            practice = cfg.get("practice", "name", fallback="Virtus Health & Medical")
            cancel_n = cfg.get("templates", "cancel_number", fallback="+27 21 439 1555")
            reply = (
                f"Sorry, something went wrong on our end. "
                f"Please call us on {cancel_n}.\n— {practice}"
            )
            # Log the error reply
            try:
                from engine import live_sync as ls
                ls.log_message(from_number, "outbound", reply)
            except Exception:
                pass

        if reply:
            result = send_whatsapp(from_number, reply, cfg)
            status = "sent" if result.get("success") else "failed"
            print(f"  -> [{status}] {reply[:80]}{'...' if len(reply) > 80 else ''}")
            # Log the outbound reply (receptionist already logs most paths,
            # but this catches any reply generated outside handle_message)
            try:
                from engine import live_sync as ls
                ls.log_message(from_number, "outbound", reply)
                # If receptionist just completed a booking, re-resolve so the
                # newly-logged outbound row also carries booking_made status.
                booking_id = ls.get_resolved_booking_id(from_number)
                if booking_id:
                    ls.resolve_conversation(from_number, "booking_made", booking_id)
            except Exception:
                pass

        save_to_inbox(from_number, body, "conversation")

        self.send_response(200)
        self.send_header("Content-Type", "text/xml")
        self.end_headers()
        self.wfile.write(b"<?xml version='1.0' encoding='UTF-8'?><Response></Response>")

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(BASE_DIR))
    from engine import triage_agent
    triage_agent.init_triage_table()

    cfg  = load_config()
    sid  = cfg.get("twilio", "account_sid", fallback="")
    live = sid.startswith("AC") and not sid.startswith("AC_PLACEHOLDER")
    doctor_num = cfg.get("practice", "doctor_notify_number", fallback="NOT SET")

    print(f"\n{'='*60}")
    print("  CadenceWorks — Virtus Health & Medical Triage Agent")
    print(f"{'='*60}")
    print(f"  Port:           {PORT}")
    anthropic_key = cfg.get("anthropic", "api_key", fallback="")
    llm_live = anthropic_key and anthropic_key != "YOUR_API_KEY_HERE"

    print(f"  Twilio:         {'Connected ✓' if live else 'Not configured — demo mode'}")
    print(f"  Agent mode:     {'LLM (Claude) ✓' if llm_live else 'LLM — API key not set'}")
    print(f"  Doctor notify:  {doctor_num}")
    print(f"  Endpoint:       http://localhost:{PORT}/whatsapp/incoming")
    print(f"\n  To expose publicly:")
    print(f"    ngrok http {PORT}")
    print(f"\n  Then in Twilio Console set WhatsApp sandbox webhook to:")
    print(f"    https://<ngrok-url>/whatsapp/incoming")
    print(f"\n  Handles: house calls, tele-consults, FAQs, deflections")
    print(f"{'='*60}\n")

    server = HTTPServer(("0.0.0.0", PORT), TwilioWebhookHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
