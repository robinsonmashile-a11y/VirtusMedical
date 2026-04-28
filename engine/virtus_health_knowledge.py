"""
CadenceWorks — Virtus Health Knowledge Base
============================================
Source of truth for the AI Booking Agent and all analytics.
Data verified from virtusmed.co.za — April 2025.

Update this file when:
  - Prices change
  - Doctors join or leave
  - Hours change
  - Services are added or removed
"""

# ── Practice details ───────────────────────────────────────────────────────────

PRACTICE = {
    "name":        "Virtus Health & Medical",
    "address":     "3rd Floor, The Point Mall, 76 Regent Road, Sea Point, Cape Town, 8005",
    "phone":       "+27 21 439 1555",
    "email":       "reception@virtusmed.co.za",
    "website":     "virtusmed.co.za",
    "booking_url": "recomed.co.za/by-name/virtus-health-and-medical",
    "instagram":   "@virtus_health_ct",
    "hours": {
        "monday":    "08:30 – 17:30",
        "tuesday":   "08:30 – 17:30",
        "wednesday": "08:30 – 17:30",
        "thursday":  "08:30 – 17:30",
        "friday":    "08:30 – 16:00",
        "saturday":  "08:30 – 12:00",
        "sunday":    "Closed",
        "after_hours": (
            "Prior arranged after-hours consultations and house calls are available "
            "and charged at higher rates."
        ),
    },
    "founded": "2013",
    "description": (
        "A premium multi-doctor general practice based at The Point Mall in Sea Point, "
        "Cape Town. Founded in 2013 by Dr Ryan Jankelowitz and Dr Jane Benjamin. "
        "Their vision is to incorporate every aspect of general practice and family "
        "medicine with health prevention and promotion strategies, ensuring patients "
        "achieve optimal health and wellness throughout all life stages."
    ),
    "medical_aid": (
        "Virtus Health is not contracted to any medical aid. "
        "Patients are responsible to settle their consultation on the day of service "
        "and claim back from their medical aid themselves."
    ),
    "parking": "Secure parking available in The Point Mall basement — entrance on Regent Road.",
    "extras": (
        "In-house dietician and counsellor available. "
        "Treatment of addictions and eating disorders. "
        "Visa medicals (South African), PDP forms, occupational medicals. "
        "Referrals for radiology and pathology services."
    ),
}


# ── Doctors ────────────────────────────────────────────────────────────────────

DOCTORS = [
    {
        "name":       "Dr Ryan Jankelowitz",
        "role":       "Co-Founder & General Practitioner",
        "interests":  ["General practice", "Sports medicine", "Paediatrics", "Holistic medicine"],
        "routing":    ["sports", "injury", "paediatric", "children", "kids", "holistic",
                       "general", "gp", "sick", "flu", "family"],
        "note":       "Co-founder of Virtus Health. Known for a holistic, patient-centred approach.",
    },
    {
        "name":       "Dr Jane Benjamin",
        "role":       "Co-Founder & General Practitioner",
        "interests":  ["Women's health", "Children's health", "Family medicine"],
        "routing":    ["women", "female", "contraception", "pregnancy", "fertility",
                       "smear", "breast", "family", "children", "kids"],
        "note":       "Co-founder of Virtus Health. Specialises in women's and children's health.",
    },
    {
        "name":       "Dr Stefan Bezuidenhout",
        "role":       "General Practitioner — Aesthetics & Integrative Medicine",
        "interests":  ["Medical aesthetics", "Anti-ageing", "Botox", "Dermal fillers",
                       "Chemical peels", "Threads", "Integrative medicine", "Fitness"],
        "routing":    ["aesthetics", "botox", "fillers", "anti-ageing", "aging", "ageing",
                       "integrative", "peels", "threads", "beauty", "cosmetic", "age-reversal",
                       "age reversal", "iv", "infusion", "drip"],
        "note":       (
            "Graduated University of the Free State. Completed internship at Johannesburg "
            "General Hospital. Moved to Cape Town 2013. Holds diplomas in age-reversal and "
            "aesthetics. Keen interest in integrative medicine and fitness."
        ),
    },
    {
        "name":       "Dr Stacey Fine",
        "role":       "General Practitioner",
        "interests":  ["Women's health", "Children's health", "Family medicine",
                       "Haematology", "Chronic medicine"],
        "routing":    ["women", "female", "children", "kids", "baby", "smear",
                       "contraception", "pregnancy", "fertility", "breast", "paediatric"],
        "note":       (
            "Graduated Wits University 2010. Internship and community service at "
            "New Somerset and Vanguard hospitals. USMLE 2018. Experience in haematology, "
            "stem cell transplant, chronic medicine. Interest in women's and children's health."
        ),
    },
    {
        "name":       "Dr Marc Davidowitz",
        "role":       "General Practitioner",
        "interests":  ["General practice", "Family medicine", "Chronic care"],
        "routing":    ["general", "gp", "sick", "flu", "chronic", "family", "prescription",
                       "referral", "repeat", "medication"],
        "note":       "Graduated UCT Medical School 2011 with Distinction and First Class Honours throughout. Highly rated by patients.",
    },
]

# Flat list for scheduling — all 5 doctors
DEFAULT_DOCTORS = [
    {
        "name":  "Dr Ryan Jankelowitz",
        "slots": ["08:30", "09:00", "09:30", "10:00", "11:00", "14:00", "15:00", "16:00", "17:00"],
    },
    {
        "name":  "Dr Jane Benjamin",
        "slots": ["08:30", "09:00", "10:00", "11:00", "14:00", "15:00", "16:00", "17:00"],
    },
    {
        "name":  "Dr Stefan Bezuidenhout",
        "slots": ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00", "17:00"],
    },
    {
        "name":  "Dr Stacey Fine",
        "slots": ["08:30", "09:00", "10:00", "11:00", "14:00", "15:00", "16:00", "17:00"],
    },
    {
        "name":  "Dr Marc Davidowitz",
        "slots": ["08:30", "09:00", "09:30", "10:00", "11:00", "13:00", "14:00", "15:00", "16:00", "17:00"],
    },
]

# ── Smart doctor routing ────────────────────────────────────────────────────────

DOCTOR_ROUTING_RULES = {
    # Aesthetics → Dr Stefan
    "aesthetics":    "Dr Stefan Bezuidenhout",
    "botox":         "Dr Stefan Bezuidenhout",
    "fillers":       "Dr Stefan Bezuidenhout",
    "filler":        "Dr Stefan Bezuidenhout",
    "anti-ageing":   "Dr Stefan Bezuidenhout",
    "anti ageing":   "Dr Stefan Bezuidenhout",
    "age-reversal":  "Dr Stefan Bezuidenhout",
    "age reversal":  "Dr Stefan Bezuidenhout",
    "chemical peel": "Dr Stefan Bezuidenhout",
    "threads":       "Dr Stefan Bezuidenhout",
    "cosmetic":      "Dr Stefan Bezuidenhout",
    "integrative":   "Dr Stefan Bezuidenhout",
    "iv therapy":    "Dr Stefan Bezuidenhout",
    "iv drip":       "Dr Stefan Bezuidenhout",
    "infusion":      "Dr Stefan Bezuidenhout",
    "drip":          "Dr Stefan Bezuidenhout",
    # Sports / paediatrics → Dr Ryan
    "sports":        "Dr Ryan Jankelowitz",
    "sport":         "Dr Ryan Jankelowitz",
    "injury":        "Dr Ryan Jankelowitz",
    "paediatric":    "Dr Ryan Jankelowitz",
    # Women's health → Dr Jane or Dr Stacey
    "pregnancy":     "Dr Jane Benjamin",
    "fertility":     "Dr Jane Benjamin",
    "smear":         "Dr Jane Benjamin",
    "contraception": "Dr Jane Benjamin",
    "breast check":  "Dr Jane Benjamin",
    # Children / baby → Dr Stacey
    "baby":          "Dr Stacey Fine",
    "children":      "Dr Stacey Fine",
    "child":         "Dr Stacey Fine",
    "kids":          "Dr Stacey Fine",
    "infant":        "Dr Stacey Fine",
    "vaccination":   "Dr Stacey Fine",
    "vaccine":       "Dr Stacey Fine",
    "immunisation":  "Dr Stacey Fine",
}


# ── Service clinics (as per website) ──────────────────────────────────────────

SERVICES = {
    "General Health & Wellness": {
        "description": (
            "All aspects of general practice and family medicine — whether you're feeling unwell, "
            "need medical treatment, a repeat prescription, medical advice, or specialist referral. "
            "Also includes visa medicals, PDP forms, occupational health, "
            "in-house dietician, counsellor, addiction and eating disorder treatment."
        ),
        "services": [
            {"name": "GP Consultation",            "fee": 750,  "duration": 20},
            {"name": "Extended Consultation",      "fee": 1100, "duration": 40},
            {"name": "Tele-Consultation",          "fee": 600,  "duration": 20},
            {"name": "House Call",                 "fee": 2500, "duration": 45},
            {"name": "After-Hours House Call",     "fee": 3500, "duration": 45},
            {"name": "Visa Medical",               "fee": 1800, "duration": 45},
            {"name": "Occupational Medical",       "fee": 1200, "duration": 30},
            {"name": "Dietician Consultation",     "fee": 850,  "duration": 45},
            {"name": "Counselling Session",        "fee": 950,  "duration": 50},
        ],
    },
    "Virtus Infusion Clinic": {
        "description": (
            "IV therapy formulated to provide your body with the vitamins, nutrients, "
            "fluids, electrolytes and antioxidants that you need. Give your body an instant boost."
        ),
        "services": [
            {"name": "Hydration Drip",             "fee": 1800, "duration": 60},
            {"name": "Vitamin Boost Drip",         "fee": 2200, "duration": 60},
            {"name": "Immunity Drip",              "fee": 2500, "duration": 60},
            {"name": "Energy & Recovery Drip",     "fee": 2400, "duration": 60},
            {"name": "Antioxidant Drip",           "fee": 2600, "duration": 60},
            {"name": "Custom IV Infusion",         "fee": 3000, "duration": 75},
        ],
    },
    "Virtus Baby Clinic": {
        "description": (
            "A range of services to ensure your bundle of joy remains happy and healthy — "
            "from expert advice to vaccinating your baby against infectious diseases."
        ),
        "services": [
            {"name": "Baby Wellness Visit",        "fee": 850,  "duration": 30},
            {"name": "Paediatric Consultation",    "fee": 750,  "duration": 20},
            {"name": "Immunisation / Vaccination", "fee": 450,  "duration": 15},
            {"name": "Newborn Check",              "fee": 850,  "duration": 30},
        ],
    },
    "Virtus Aesthetics Clinic": {
        "description": (
            "Cost-effective, non-surgical methods for addressing and delaying the ageing process. "
            "Botox, dermal fillers, chemical peels, threads, and more — with Dr Stefan Bezuidenhout."
        ),
        "services": [
            {"name": "Aesthetics Consultation",    "fee": 700,  "duration": 30},
            {"name": "Botox",                      "fee": 2800, "duration": 30},
            {"name": "Dermal Fillers",             "fee": 5500, "duration": 45},
            {"name": "Chemical Peel",              "fee": 1800, "duration": 45},
            {"name": "Threads",                    "fee": 4500, "duration": 60},
            {"name": "Integrative Medicine Consult","fee": 1200,"duration": 45},
        ],
    },
    "Woman Wellness": {
        "description": (
            "Women's health and wellness including breast checks, smear tests, "
            "contraception and family planning advice, pregnancy and fertility related "
            "advice and referral."
        ),
        "services": [
            {"name": "Women's Health Consultation","fee": 850,  "duration": 30},
            {"name": "Smear Test (PAP)",           "fee": 950,  "duration": 20},
            {"name": "Breast Check",               "fee": 750,  "duration": 20},
            {"name": "Contraception Consultation", "fee": 750,  "duration": 20},
            {"name": "Pregnancy Consultation",     "fee": 950,  "duration": 30},
            {"name": "Fertility Consultation",     "fee": 1200, "duration": 45},
        ],
    },
}

# Flat appointment type list for booking agent
APPOINTMENT_TYPES = [
    svc["name"]
    for pillar in SERVICES.values()
    for svc in pillar["services"]
]

# ── Cross-sell sequences ───────────────────────────────────────────────────────

CROSS_SELL_SEQUENCES = {
    "GP Consultation": {
        "next_service": "Virtus Infusion Clinic",
        "message": (
            "Hi {name}! Hope you're feeling better after your visit. "
            "Did you know we have the Virtus Infusion Clinic? "
            "From hydration drips to vitamin boosts — patients love the instant energy boost. "
            "Reply IVINFO for details or BOOK to schedule."
        ),
    },
    "Hydration Drip": {
        "next_service": "Virtus Aesthetics Clinic",
        "message": (
            "Hi {name}! Great seeing you at the Virtus Infusion Clinic. "
            "Did you know Dr Stefan also runs our Aesthetics Clinic? "
            "Botox, fillers, chemical peels — non-surgical, effective age-reversal. "
            "Reply AESTHETICS to find out more."
        ),
    },
    "Botox": {
        "next_service": "Virtus Infusion Clinic",
        "message": (
            "Hi {name}! Great seeing you at the Virtus Aesthetics Clinic. "
            "Many of our aesthetics patients also love our infusion clinic — "
            "antioxidant and vitamin drips work beautifully alongside aesthetic treatments. "
            "Reply DRIP to find out more."
        ),
    },
    "Baby Wellness Visit": {
        "next_service": "Woman Wellness",
        "message": (
            "Hi {name}! Hope your little one is doing well after their visit. "
            "As a reminder, we also offer a full Woman Wellness service — "
            "smear tests, breast checks, contraception advice, and more. "
            "Reply WOMENS to find out more or BOOK to schedule."
        ),
    },
}

# ── FAQs ───────────────────────────────────────────────────────────────────────

FAQS = {
    "parking": (
        "The Point Mall has secure basement parking. "
        "Entrance on Regent Road, Sea Point."
    ),
    "medical_aid": (
        "We are not contracted to any medical aid. "
        "You pay on the day and we give you an invoice to claim back yourself."
    ),
    "house_calls": (
        "Yes, we offer prior-arranged house calls and after-hours consultations "
        "at higher rates. Book via WhatsApp and we'll arrange with the on-call doctor."
    ),
    "iv_therapy": (
        "Our Infusion Clinic offers hydration, vitamin boost, immunity, energy, "
        "antioxidant and custom IV drips. Sessions take 45–75 minutes. From R1,800."
    ),
    "aesthetics": (
        "Dr Stefan Bezuidenhout runs our Aesthetics Clinic. "
        "Botox from R2,800, dermal fillers from R5,500, chemical peels from R1,800, threads from R4,500. "
        "Book a consultation first to discuss your goals."
    ),
    "baby_clinic": (
        "Our Baby Clinic covers wellness visits, immunisations, newborn checks, "
        "and general paediatric consultations. Friendly and experienced with little ones."
    ),
    "womens_health": (
        "Our Woman Wellness service covers smear tests, breast checks, "
        "contraception, pregnancy and fertility advice and referrals."
    ),
    "visa_medicals": (
        "Yes, we offer South African Visa Medicals, PDP forms, "
        "and other occupational medicals."
    ),
    "dietician": (
        "We have an in-house dietician and counsellor. "
        "We also treat addictions and eating disorders."
    ),
}
