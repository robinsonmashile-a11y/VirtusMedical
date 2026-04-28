"""
CadenceWorks — Fluid Medical Knowledge Base
============================================
Single source of truth for everything the AI Triage Agent knows
about Fluid Medical. Update this file when:
  - Prices change
  - Doctors join or leave
  - Hours change
  - New services are added
  - FAQs need updating

This is imported by receptionist.py and injected into the
system prompt for every conversation.
"""

# ── Practice details ───────────────────────────────────────────────────────────

PRACTICE = {
    "name":        "Fluid Medical",
    "address":     "22 Hope Street, Gardens, Cape Town",
    "phone":       "021 200 2121",
    "whatsapp":    "076 577 9287",
    "email":       "info@fluidmedical.co.za",
    "website":     "www.fluidmedical.co.za",
    "booking_url": "flm.healthaccess.co.za",
    "hours": {
        "monday_friday": "08:00 – 19:00",
        "saturday":      "09:00 – 16:00",
        "sunday":        "Closed (house calls and tele-consults available 24/7)",
    },
    "founded": "February 2026",
    "description": (
        "A modern multi-doctor general practice built around four pillars: "
        "Health, Aesthetics, Longevity, and Sports Medicine. "
        "Founded by Dr Carl Arndt. Based in Gardens, Cape Town."
    ),
    "medical_aid": (
        "Fluid Medical does not bill medical aid directly. "
        "We provide a detailed invoice after your consultation "
        "which you can submit to your medical aid for reimbursement."
    ),
}


# ── Team ───────────────────────────────────────────────────────────────────────

DOCTORS = [
    {
        "name":      "Dr Carl Arndt",
        "role":      "Founder & Medical Doctor",
        "interests": ["Family medicine", "Longevity", "Preventative medicine",
                      "Medical aesthetics", "Minor surgical procedures"],
        "education": "MBChB (Cum Laude) — Stellenbosch University",
        "note":      "Originally from Germany, raised in South Africa.",
    },
    {
        "name":      "Dr Mudiwa Llobell",
        "role":      "Medical Doctor — Sports & Exercise Medicine",
        "interests": ["Sports-related injuries", "Performance optimisation",
                      "Strength and conditioning", "Exercise prescription"],
        "education": "MBChB — Stellenbosch University; Masters in Sports & Exercise Medicine — UCT (in progress)",
        "note":      "Born in Spain, grew up in Durban.",
    },
    {
        "name":      "Dr Roseanne Allanson",
        "role":      "Medical Doctor — General Practice",
        "interests": ["Minor surgical procedures", "Medical aesthetics",
                      "Chronic care", "Dermatology (rashes and acne)"],
        "education": "BSc Human Life Sciences (Hons) + MBChB — Stellenbosch University",
        "note":      "",
    },
    {
        "name":      "Dr Maurice Human",
        "role":      "Medical Doctor — General Practice",
        "interests": ["Medical aesthetics", "Minor surgical procedures",
                      "Mental health", "Preventative medicine"],
        "education": "MBChB (Cum Laude) — Stellenbosch University",
        "note":      "",
    },
    {
        "name":      "Dr Raheez Morta",
        "role":      "Medical Doctor — General Practice",
        "interests": ["General practice", "Mental health",
                      "Chronic disease management", "Holistic medicine"],
        "education": "MBChB — Stellenbosch University; further training in medicine and psychiatry (in progress)",
        "note":      "Cape Town born and raised.",
    },
    {
        "name":      "Dr Nausheenah Parker",
        "role":      "Medical Doctor — General Practice",
        "interests": ["Family medicine", "Mental health", "Trauma care"],
        "education": "MBChB — Stellenbosch University; community service at rural district hospital",
        "note":      "",
    },
    {
        "name":      "Dr Lauren Pienaar",
        "role":      "Medical Doctor — General Practice",
        "interests": ["Women's health", "Mental health", "Ultrasonography",
                      "Minor procedures", "General practice"],
        "education": "MBChB (Cum Laude) — Stellenbosch University",
        "note":      "Cape Town born and educated.",
    },
    {
        "name":      "Chad Baxter",
        "role":      "Biokineticist — Sport & Exercise",
        "interests": ["Sport and exercise rehabilitation", "Biokinesiology"],
        "education": "",
        "note":      "",
    },
]


# ── Services ───────────────────────────────────────────────────────────────────
# Full service catalogue with fees, descriptions, and pillar grouping.
# The triage agent only books HOUSE_CALL and TELE_CONSULT.
# All other services are deflected to the booking URL or phone.

SERVICES = {

    # ── HEALTH pillar ──────────────────────────────────────────────────────────

    "gp_consult": {
        "name":        "In-Depth General Consultation",
        "pillar":      "Health",
        "fee":         "R950",
        "description": "Thorough, unhurried in-person GP consult for acute and chronic conditions.",
        "book_via":    "website or call",
        "agent_books": False,
    },
    "house_call": {
        "name":        "24/7 House Call",
        "pillar":      "Health",
        "fee":         "From R2,750",
        "description": (
            "Full GP consultation delivered to your home, hotel, or office "
            "anywhere in the greater Cape Town area. Available 24 hours, 7 days a week. "
            "Includes detailed history, physical examination, on-site investigations "
            "(blood collection, point-of-care testing, portable ultrasound), and "
            "on-site treatment where needed (IV fluids, IV/IM medications, "
            "nebulisation, wound care). "
            "Useful for: acute infections, severe dehydration, migraines, "
            "elderly or immobile patients, post-operative review, "
            "hangovers requiring medical IV fluids, or anyone who prefers "
            "care at home. "
            "This is NOT an emergency service. For chest pain, stroke symptoms, "
            "severe trauma, or collapse — call an ambulance (10177) immediately."
        ),
        "book_via":    "agent",
        "agent_books": True,
        "collect": [
            "full_name",
            "phone",
            "address",       # full street address for the doctor to travel to
            "complaint",     # brief description of what's wrong
            "preferred_time", # ASAP or a preferred time window
        ],
    },
    "tele_consult": {
        "name":        "Tele-Consult",
        "pillar":      "Health",
        "fee":         "R600",
        "description": (
            "Secure 30-minute video consultation with a Fluid Medical doctor. "
            "Available 24 hours, 7 days a week. "
            "Suitable for: mild flu, common cold, gastroenteritis, headaches, "
            "uncomplicated UTIs, certain STIs, skin conditions (rashes, eczema, "
            "acne follow-up), mild anxiety, sleep disturbances, repeat scripts, "
            "and sick notes. "
            "NOT suitable for conditions requiring physical examination, "
            "imaging, or urgent intervention. If your condition is more serious "
            "than expected, the doctor will advise you to come in, request a "
            "house call, or go to hospital."
        ),
        "book_via":    "agent",
        "agent_books": True,
        "collect": [
            "full_name",
            "phone",
            "complaint",      # brief description of symptoms
            "preferred_time", # ASAP or preferred time window
        ],
    },
    "tele_consult_weight_loss": {
        "name":        "Medical Weight Loss Consult",
        "pillar":      "Health",
        "fee":         "R1,950",
        "description": "Doctor-led, personalised weight loss consultation. In-person only.",
        "book_via":    "website or call",
        "agent_books": False,
    },
    "iv_therapy": {
        "name":        "Intravenous Treatments",
        "pillar":      "Health",
        "fee":         "From R850",
        "description": "Evidence-based IV treatments for hydration, vitamins, and minerals. In-person only.",
        "book_via":    "website or call",
        "agent_books": False,
    },
    "minor_surgical": {
        "name":        "Minor Surgical Procedures",
        "pillar":      "Health",
        "fee":         "From R2,000",
        "description": "In-office lump, bump, and lesion removal and other minor procedures.",
        "book_via":    "website or call",
        "agent_books": False,
    },

    # ── AESTHETICS pillar ─────────────────────────────────────────────────────

    "botox_aesthetic": {
        "name":    "Aesthetic Botulinum Toxin",
        "pillar":  "Aesthetics",
        "fee":     "From R1,000",
        "services": ["Frown lines (from R2,000)", "Forehead lines (from R1,600)",
                     "Crow's feet (from R1,600)", "Eyebrow lift (R1,000)",
                     "Jaw slimming (from R2,000)", "Down-turned smile (R1,000)",
                     "Gummy smile (R1,000)", "Neck lines / platysma bands (from R2,000)",
                     "Bar code lines (from R1,000)", "Baby Botulinum toxin (from R1,000)"],
        "book_via":    "website or call",
        "agent_books": False,
    },
    "botox_functional": {
        "name":    "Functional Botulinum Toxin",
        "pillar":  "Aesthetics",
        "services": ["Teeth grinding (from R2,000)", "Hyperhidrosis / sweating (R10,000)",
                     "Tension headaches (R2,000)"],
        "book_via":    "website or call",
        "agent_books": False,
    },
    "prp_aesthetics": {
        "name":    "PRP — Aesthetics",
        "pillar":  "Aesthetics",
        "services": ["PRP skin rejuvenation (from R4,000)", "PRP hair regrowth (R4,000)",
                     "PRP vaginal rejuvenation (R8,000)", "PRP erectile dysfunction (R8,000)"],
        "book_via":    "website or call",
        "agent_books": False,
    },
    "fillers": {
        "name":    "Fillers — Restylane Hyaluronic Acid",
        "pillar":  "Aesthetics",
        "services": ["Jawline / chin / cheekbones (from R4,000)", "Lip rejuvenation (R4,000)",
                     "Penile filler (R10,000)"],
        "book_via":    "website or call",
        "agent_books": False,
    },
    "sculptra": {
        "name":    "Sculptra Biostimulator",
        "pillar":  "Aesthetics",
        "services": ["Sculptra per vial (R7,000)", "Sculptra 2 vials (R13,000)",
                     "Sculptra 4 vials (R24,000)"],
        "book_via":    "website or call",
        "agent_books": False,
    },
    "microneedling": {
        "name":    "Microneedling",
        "pillar":  "Aesthetics",
        "services": ["Microneedling (R3,000)", "Microneedling with PRP (R5,000)"],
        "book_via":    "website or call",
        "agent_books": False,
    },
    "mesotherapy": {
        "name":    "Mesotherapy",
        "pillar":  "Aesthetics",
        "services": ["Hyaluronic acid skinbooster (from R4,000)", "Microtox (R3,000)",
                     "Combined ultra skin rejuvenation (from R6,000)"],
        "book_via":    "website or call",
        "agent_books": False,
    },
    "acne": {
        "name":    "Acne and Acne Scarring",
        "pillar":  "Aesthetics",
        "services": ["Acne scarring subcision (R3,500)", "Subcision with skinbooster (R5,000)",
                     "Keloid removal (R4,000)"],
        "book_via":    "website or call",
        "agent_books": False,
    },

    # ── LONGEVITY pillar ──────────────────────────────────────────────────────

    "longevity_consult": {
        "name":        "Longevity Consult",
        "pillar":      "Longevity",
        "fee":         "R750",
        "description": "Initial longevity-focused consultation to assess healthspan and long-term risk.",
        "book_via":    "website or call",
        "agent_books": False,
    },
    "biological_age": {
        "name":        "Biological Age Assessment",
        "pillar":      "Longevity",
        "fee":         "R5,500",
        "description": "Advanced testing to determine biological age and guide personalised longevity strategies.",
        "book_via":    "website or call",
        "agent_books": False,
    },
    "biomarker_panel": {
        "name":        "Comprehensive Biomarker Panel",
        "pillar":      "Longevity",
        "fee":         "R3,500",
        "description": "Extensive laboratory testing for metabolic, hormonal, and disease risk markers.",
        "book_via":    "website or call",
        "agent_books": False,
    },
    "longevity_subscription_monthly": {
        "name":        "Longevity Monthly Subscription",
        "pillar":      "Longevity",
        "fee":         "R8,500/month",
        "description": "Ongoing preventative healthcare programme.",
        "book_via":    "website or call",
        "agent_books": False,
    },
    "longevity_subscription_yearly": {
        "name":        "Longevity Yearly Subscription",
        "pillar":      "Longevity",
        "fee":         "R60,000/year",
        "description": "Annual preventative healthcare programme.",
        "book_via":    "website or call",
        "agent_books": False,
    },
    "targeted_longevity": {
        "name":    "Targeted Longevity Interventions",
        "pillar":  "Longevity",
        "services": ["Neurodegenerative disease prevention", "Cancer prevention consult",
                     "Cardiovascular disease prevention", "Metabolic disease prevention"],
        "book_via":    "website or call",
        "agent_books": False,
    },

    # ── SPORTS pillar ─────────────────────────────────────────────────────────

    "sports_consult": {
        "name":        "Sports Consultation",
        "pillar":      "Sports",
        "description": "Doctor-led consultation for sports injuries, performance, and return to activity.",
        "book_via":    "website or call",
        "agent_books": False,
    },
    "prp_sports": {
        "name":    "PRP — Sports Injection",
        "pillar":  "Sports",
        "services": ["PRP osteoarthritis", "PRP ligament injuries", "PRP tendon injuries",
                     "PRP muscle injuries", "PRP overuse injuries"],
        "book_via":    "website or call",
        "agent_books": False,
    },
    "intra_articular": {
        "name":    "Intra-articular Injections",
        "pillar":  "Sports",
        "services": ["Cortisone injection", "Hyaluronic acid osteoarthritis treatment"],
        "book_via":    "website or call",
        "agent_books": False,
    },
    "concussion": {
        "name":        "Concussion Assessment & Treatment",
        "pillar":      "Sports",
        "description": "Evidence-based concussion assessment and medically supervised return-to-play.",
        "book_via":    "website or call",
        "agent_books": False,
    },
    "chronic_disease": {
        "name":        "Long-Term Chronic Disease Management",
        "pillar":      "Sports",
        "description": "Personalised chronic condition management for athletes and general patients.",
        "book_via":    "website or call",
        "agent_books": False,
    },
}


# ── Triage keywords ────────────────────────────────────────────────────────────
# Used by the agent to detect what kind of service the patient wants.

HOUSE_CALL_KEYWORDS = [
    "house call", "home visit", "come to me", "come to my house",
    "come to my home", "visit me", "doctor at home", "home call",
    "at home", "to my place", "my address", "send a doctor",
    "housecall", "callout", "call out", "call-out",
    "home doctor", "doctor home", "huis besoek", "dokter huis",
]

TELE_CONSULT_KEYWORDS = [
    "tele", "teleconsult", "tele-consult", "tele consult",
    "online consult", "video consult", "virtual consult",
    "video call", "online doctor", "remote consult",
    "over the phone", "phone consult", "zoom", "teams",
    "don't want to come in", "cant come in", "can't come in",
    "from home", "at home consult",
]

EMERGENCY_KEYWORDS = [
    "emergency", "chest pain", "heart attack", "stroke", "collapse",
    "unconscious", "not breathing", "severe bleeding", "ambulance",
    "dying", "can't breathe", "shortness of breath", "convulsion",
    "seizure", "overdose", "poisoning",
]

DEFLECT_KEYWORDS = [
    "botox", "filler", "sculptra", "prp", "microneedling", "aesthetics",
    "longevity", "biomarker", "biological age", "sports", "injury",
    "weight loss", "iv therapy", "drip", "intravenous", "surgical",
    "acne", "scar", "hair loss", "sweating", "headache treatment",
    "teeth grinding", "anti-ageing", "anti aging",
]


# ── FAQ answers ────────────────────────────────────────────────────────────────
# Plain-text answers the agent uses to respond to common questions
# before moving the patient into a booking flow.

FAQS = {

    "hours": (
        "🕐 *Fluid Medical hours:*\n\n"
        "Monday – Friday: 08:00 – 19:00\n"
        "Saturday: 09:00 – 16:00\n"
        "Sunday: Closed\n\n"
        "House calls and tele-consults are available *24/7*, every day including Sundays and public holidays."
    ),

    "address": (
        "📍 *Fluid Medical*\n"
        "22 Hope Street, Gardens, Cape Town\n\n"
        "For in-practice appointments, please book via our website: www.fluidmedical.co.za\n"
        "or call us on 021 200 2121."
    ),

    "medical_aid": (
        "Fluid Medical is a private practice and does not bill medical aid directly. "
        "We provide a detailed invoice after your consultation which you can submit "
        "to your medical aid for reimbursement. "
        "If you have questions about this, call us on 021 200 2121."
    ),

    "house_call_cost": (
        "A house call starts from *R2,750*. "
        "This covers the full consultation including examination, "
        "on-site investigations, and any treatments administered during the visit "
        "(such as IV fluids or medications). "
        "The final fee may vary depending on what is required during the visit."
    ),

    "house_call_area": (
        "We cover the *greater Cape Town area*. "
        "Availability is confirmed when you request a booking — "
        "the on-call doctor will confirm they can reach your address."
    ),

    "house_call_time": (
        "House calls are available *24/7*. "
        "Once your request is received by the doctor, "
        "they will contact you directly to confirm an estimated arrival time."
    ),

    "house_call_what_included": (
        "A house call includes a full GP consultation at your home:\n\n"
        "• Detailed medical history and physical examination\n"
        "• On-site blood collection and point-of-care testing\n"
        "• Portable ultrasound where needed\n"
        "• IV fluids, IV/IM medications, nebulisation, and wound care where clinically appropriate\n\n"
        "It is the same standard of care as an in-clinic visit, brought to you."
    ),

    "house_call_emergency": (
        "⚠️ The house call service is for *urgent but non-life-threatening conditions*.\n\n"
        "If you or someone nearby is experiencing chest pain, stroke symptoms, "
        "severe trauma, difficulty breathing, or collapse — "
        "please call an ambulance immediately on *10177* (ER24) or *112*.\n\n"
        "Do not wait for a house call in these situations."
    ),

    "tele_consult_cost": (
        "A tele-consult costs *R600* and lasts approximately 30 minutes. "
        "It is a secure video call with one of our doctors."
    ),

    "tele_consult_what_for": (
        "A tele-consult is suitable for:\n\n"
        "• Mild flu or common cold\n"
        "• Gastroenteritis\n"
        "• Headaches\n"
        "• Uncomplicated urinary tract infections (UTIs)\n"
        "• Certain sexually transmitted infections\n"
        "• Skin conditions (rashes, eczema, acne follow-up)\n"
        "• Mild anxiety or sleep disturbances\n"
        "• Repeat prescriptions and chronic medication scripts\n"
        "• Sick notes\n\n"
        "If your condition requires a physical examination or urgent care, "
        "the doctor will advise you to come in or arrange a house call."
    ),

    "tele_consult_how": (
        "Once your booking is confirmed, the on-call doctor will contact you "
        "via WhatsApp or phone call at your requested time to start the video consultation. "
        "Make sure you are in a quiet, well-lit space with a stable internet connection."
    ),

    "doctors": (
        "Fluid Medical has 8 doctors across our four pillars:\n\n"
        "• Dr Carl Arndt — Founder, family medicine, longevity, aesthetics\n"
        "• Dr Mudiwa Llobell — Sports & exercise medicine\n"
        "• Dr Roseanne Allanson — General practice, minor procedures, aesthetics\n"
        "• Dr Maurice Human — General practice, aesthetics, mental health\n"
        "• Dr Raheez Morta — General practice, mental health, chronic disease\n"
        "• Dr Nausheenah Parker — General practice, family medicine, trauma\n"
        "• Dr Lauren Pienaar — General practice, women's health, ultrasonography\n"
        "• Chad Baxter — Biokineticist, sport & exercise\n\n"
        "For house calls and tele-consults, the next available on-call doctor will assist you."
    ),

    "deflect_other_services": (
        "For aesthetics, longevity, sports medicine, and in-practice GP appointments, "
        "please book via our website at *www.fluidmedical.co.za* "
        "or call us on *021 200 2121* during practice hours.\n\n"
        "This WhatsApp line handles house calls and tele-consults only."
    ),
}


# ── System prompt builder ──────────────────────────────────────────────────────

def build_system_prompt():
    """
    Returns the complete system prompt string to inject into the
    AI agent for every Fluid Medical conversation.
    """

    doctors_list = "\n".join(
        f"  - {d['name']} ({d['role']}): {', '.join(d['interests'][:2])}"
        for d in DOCTORS
    )

    house_call_collect = "\n".join(
        f"  {i+1}. {field.replace('_', ' ').title()}"
        for i, field in enumerate(SERVICES["house_call"]["collect"])
    )

    tele_collect = "\n".join(
        f"  {i+1}. {field.replace('_', ' ').title()}"
        for i, field in enumerate(SERVICES["tele_consult"]["collect"])
    )

    prompt = f"""You are the AI Triage Agent for Fluid Medical, a premium multi-doctor medical practice in Cape Town, South Africa. You operate on their WhatsApp number and handle ONLY house call and tele-consult enquiries.

Your name is not important — you represent Fluid Medical. Be warm, professional, and concise. Use plain English. You can use Afrikaans greetings if the patient uses them.

═══════════════════════════════════════
PRACTICE INFORMATION
═══════════════════════════════════════
Name:     Fluid Medical
Address:  22 Hope Street, Gardens, Cape Town
Phone:    021 200 2121
WhatsApp: 076 577 9287
Email:    info@fluidmedical.co.za
Website:  www.fluidmedical.co.za

Hours:
  Monday – Friday: 08:00 – 19:00
  Saturday:        09:00 – 16:00
  Sunday:          Closed (house calls & tele-consults available 24/7)

Medical aid: Fluid Medical does not bill medical aid directly. Patients receive a detailed invoice to submit to their medical aid for reimbursement.

═══════════════════════════════════════
YOUR SCOPE — WHAT YOU HANDLE
═══════════════════════════════════════
You ONLY assist with:
  1. House call requests (24/7, greater Cape Town, from R2,750)
  2. Tele-consult requests (24/7, video call, R600)
  3. FAQs about these two services

For ALL other services (aesthetics, longevity, sports, in-practice GP, IV therapy, weight loss, surgical procedures) — politely redirect the patient to www.fluidmedical.co.za or 021 200 2121. Do not attempt to book these.

═══════════════════════════════════════
EMERGENCY PROTOCOL
═══════════════════════════════════════
If a patient describes chest pain, stroke symptoms, collapse, severe trauma, difficulty breathing, seizures, or any life-threatening emergency — IMMEDIATELY direct them to call 10177 (ER24) or 112. Do not collect booking information. Do not delay this response.

═══════════════════════════════════════
HOUSE CALL SERVICE
═══════════════════════════════════════
Fee:          From R2,750 (includes consultation, investigations, and on-site treatment)
Availability: 24/7, greater Cape Town
Area:         Greater Cape Town — availability confirmed at time of booking

What it includes:
  - Full GP consultation at home (history, examination, diagnosis)
  - Blood collection, point-of-care testing, portable ultrasound
  - IV fluids, IV/IM medications, nebulisation, wound care where needed

Suitable for:
  - Acute infections (respiratory, gastrointestinal, urinary)
  - Severe dehydration or hangover requiring IV fluids
  - Migraines and acute pain episodes
  - Elderly or mobility-limited patients
  - Post-operative review
  - Anyone who prefers care at home

NOT for emergencies. NOT for aesthetics (book separately via website).

To collect a house call request, gather:
{house_call_collect}

═══════════════════════════════════════
TELE-CONSULT SERVICE
═══════════════════════════════════════
Fee:          R600
Duration:     ~30 minutes
Format:       Secure video call
Availability: 24/7

Suitable for:
  - Mild flu, common cold, gastroenteritis
  - Headaches
  - Uncomplicated UTIs and certain STIs
  - Skin conditions (rashes, eczema, acne follow-up)
  - Mild anxiety, sleep disturbances
  - Repeat prescriptions and chronic scripts
  - Sick notes

NOT suitable for conditions needing physical examination or urgent care. If symptoms seem more serious during the call, the doctor will refer the patient to in-person care or a house call.

To collect a tele-consult request, gather:
{tele_collect}

═══════════════════════════════════════
THE TEAM
═══════════════════════════════════════
{doctors_list}

For house calls and tele-consults, the next available on-call doctor handles the request. Patients do not select a specific doctor for these services.

═══════════════════════════════════════
YOUR CONVERSATION FLOW
═══════════════════════════════════════

STEP 1 — GREET & TRIAGE
When a patient messages, greet them warmly and identify what they need. If unclear, ask one simple question: "Are you looking for a house call or a tele-consult?"

STEP 2 — ANSWER FAQs FIRST
If the patient asks about cost, availability, what's included, or area coverage — answer their question fully before moving to booking. Do not rush them into the booking flow.

STEP 3 — SAFETY CHECK
Before collecting booking information for a house call, gently confirm: "Is this an urgent but non-life-threatening situation?" If they describe emergency symptoms, stop and direct them to emergency services.

STEP 4 — COLLECT BOOKING INFORMATION
Collect each piece of information conversationally — one question at a time, not a list. Be natural. For example: "What's your name?" then "And what's the best number to reach you on?" then "What's the address we should send the doctor to?" etc.

STEP 5 — CONFIRM SUMMARY
Once all information is collected, send a clear summary back to the patient to confirm:
  - Service type (house call or tele-consult)
  - Their name and contact number
  - For house call: the address
  - Their complaint / reason for consultation
  - Requested time (ASAP or preferred window)

Ask: "Is all of this correct? Reply YES to confirm."

STEP 6 — NOTIFY DOCTOR
After the patient confirms, send them this message:
"Thank you! ✅ Your request has been received by Fluid Medical. The on-call doctor has been notified and will contact you shortly to confirm timing. If you need to reach us urgently, call 021 200 2121."

Then trigger the doctor notification (handled separately by the notification engine).

STEP 7 — PATIENT CONFIRMATION MESSAGE
After the doctor notification is sent, confirm to the patient:
"We've let the doctor know. You'll hear from them soon. If your symptoms worsen or become an emergency, please call 10177 immediately."

═══════════════════════════════════════
TONE GUIDELINES
═══════════════════════════════════════
- Warm, calm, professional
- Concise — do not over-explain
- Never diagnose or give medical advice
- Never promise a specific arrival time — say "the doctor will confirm timing with you directly"
- If unsure about something, say "I'll make sure the doctor is aware of that when they contact you"
- Always sign off messages with "— Fluid Medical"
"""

    return prompt


# ── Doctor notification message builder ───────────────────────────────────────

def build_doctor_notification(service_type, booking_data):
    """
    Builds the WhatsApp message sent to the on-call doctor
    when a patient request is confirmed.

    Args:
        service_type: 'house_call' or 'tele_consult'
        booking_data: dict with collected patient information

    Returns:
        Formatted string ready to send via Twilio
    """
    from datetime import datetime
    timestamp = datetime.now().strftime("%d %B %Y at %H:%M")

    name    = booking_data.get("full_name", "Unknown")
    phone   = booking_data.get("phone", "Not provided")
    complaint = booking_data.get("complaint", "Not specified")
    pref_time = booking_data.get("preferred_time", "ASAP")

    if service_type == "house_call":
        address = booking_data.get("address", "Not provided")
        return (
            f"🔴 *NEW HOUSE CALL REQUEST*\n"
            f"Received: {timestamp}\n\n"
            f"👤 *Patient:* {name}\n"
            f"📞 *Phone:* {phone}\n"
            f"📍 *Address:* {address}\n"
            f"🩺 *Complaint:* {complaint}\n"
            f"🕐 *Requested time:* {pref_time}\n\n"
            f"Please contact the patient directly to confirm your ETA.\n"
            f"Then book the appointment in HealthAccess.\n\n"
            f"— CadenceWorks Triage Agent"
        )

    elif service_type == "tele_consult":
        return (
            f"🔵 *NEW TELE-CONSULT REQUEST*\n"
            f"Received: {timestamp}\n\n"
            f"👤 *Patient:* {name}\n"
            f"📞 *Phone:* {phone}\n"
            f"🩺 *Complaint:* {complaint}\n"
            f"🕐 *Requested time:* {pref_time}\n\n"
            f"Please contact the patient to confirm the video call time.\n"
            f"Then book the appointment in HealthAccess.\n\n"
            f"— CadenceWorks Triage Agent"
        )

    return f"⚠️ New patient request received from {name} ({phone}). Complaint: {complaint}. Please follow up."


# ── Patient confirmation message builder ──────────────────────────────────────

def build_patient_confirmation(service_type, booking_data):
    """
    Builds the confirmation message sent to the patient after
    the doctor has been notified.

    Args:
        service_type: 'house_call' or 'tele_consult'
        booking_data: dict with collected patient information

    Returns:
        Formatted string ready to send via Twilio
    """
    name = booking_data.get("full_name", "there")
    first_name = name.split()[0] if name and name != "there" else "there"
    pref_time = booking_data.get("preferred_time", "as soon as possible")

    if service_type == "house_call":
        return (
            f"✅ Hi {first_name}, your house call request has been received!\n\n"
            f"The on-call doctor has been notified and will contact you shortly "
            f"to confirm their estimated arrival time.\n\n"
            f"📍 We have your address on file.\n"
            f"🕐 Requested time: {pref_time}\n\n"
            f"If your symptoms worsen or become a medical emergency, "
            f"please call *10177* (ER24) immediately — do not wait for the house call.\n\n"
            f"For any queries: 021 200 2121\n\n"
            f"— Fluid Medical"
        )

    elif service_type == "tele_consult":
        return (
            f"✅ Hi {first_name}, your tele-consult request has been received!\n\n"
            f"The on-call doctor has been notified and will contact you shortly "
            f"to confirm your video call time.\n\n"
            f"🕐 Requested time: {pref_time}\n\n"
            f"Please make sure you are in a quiet, well-lit space "
            f"with a stable internet connection when the doctor calls.\n\n"
            f"For any queries: 021 200 2121\n\n"
            f"— Fluid Medical"
        )

    return (
        f"✅ Hi {first_name}, your request has been received. "
        f"A doctor will be in touch shortly.\n\n— Fluid Medical"
    )
