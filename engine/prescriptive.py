"""
CadenceWorks Analytics Engine
Layer 4: Prescriptive Analytics

Generates prioritised, data-grounded recommendations.
Each recommendation has: title, rationale, impact, action, priority.
"""

import pandas as pd
import numpy as np


def _pct(a, b):
    return round(a / b * 100, 1) if b > 0 else 0.0


def run(df: pd.DataFrame, descriptive: dict, predictive: dict) -> dict:
    """
    Generate prescriptive recommendations from descriptive + predictive outputs.
    Returns a dict with: recommendations[], agent_actions[], quick_wins[].
    """
    recommendations = []
    agent_actions   = []
    quick_wins      = []

    kpis   = descriptive.get("kpis", {})
    total  = kpis.get("total_appointments", 1)

    # ── 1. No-show rate overall ───────────────────────────────────────────────
    ns_rate = kpis.get("no_show_rate", 0)
    if ns_rate > 8:
        revenue_lost = kpis.get("revenue_lost", 0)
        # Estimate recovery: reminders reduce no-shows by 25–40%
        low_recovery  = round(revenue_lost * 0.25)
        high_recovery = round(revenue_lost * 0.40)
        recommendations.append({
            "priority":  1,
            "title":     "Deploy Risk-Based Reminder Cadence",
            "rationale": f"Your no-show rate is {ns_rate}% — above the 8% industry threshold. "
                         f"You are losing R{revenue_lost:,.0f} per month to no-shows alone.",
            "action":    "For appointments scoring High Risk (>70), trigger automated reminders "
                         "at 72hrs, 24hrs, and 4hrs via the patient's booking channel. "
                         "Low-risk appointments need only a single 24hr reminder.",
            "impact":    f"Estimated R{low_recovery:,.0f}–R{high_recovery:,.0f} monthly revenue recovery.",
            "agent":     "Reminder Agent",
        })

    # ── 2. Channel: WhatsApp high no-show ────────────────────────────────────
    noshow_by_ch = descriptive.get("noshow_by_channel", {})
    if "WhatsApp" in noshow_by_ch and noshow_by_ch.get("WhatsApp", 0) > 12:
        wa_rate   = noshow_by_ch["WhatsApp"]
        ph_rate   = noshow_by_ch.get("Phone", 0)
        diff      = round(wa_rate - ph_rate, 1)
        recommendations.append({
            "priority":  2,
            "title":     "Restrict Prime Slots for WhatsApp Bookings",
            "rationale": f"WhatsApp bookings have a {wa_rate}% no-show rate vs {ph_rate}% for phone — "
                         f"a {diff}% gap. WhatsApp patients show significantly lower commitment.",
            "action":    "Route WhatsApp bookings to non-prime slots only until the patient has "
                         "an attendance history. Require phone or online confirmation for prime slots.",
            "impact":    "Reduces prime slot waste on the highest-risk booking channel.",
            "agent":     "Slot Optimiser Agent",
        })

    # ── 3. Lead time: 15+ days ───────────────────────────────────────────────
    noshow_by_lead = descriptive.get("noshow_by_lead_time", {})
    far_rate = noshow_by_lead.get("15+ days", 0)
    near_rate = noshow_by_lead.get("0–3 days", 0)
    if far_rate > 15 and far_rate > near_rate * 1.5:
        recommendations.append({
            "priority":  3,
            "title":     "Add Confirmation Step for Far-Future Bookings",
            "rationale": f"Appointments booked 15+ days out have a {far_rate}% no-show rate vs "
                         f"{near_rate}% for same-week bookings — {round(far_rate/near_rate, 1)}× higher.",
            "action":    "For any appointment booked more than 14 days out, send a confirmation "
                         "request at the 7-day mark. If not confirmed within 24hrs, release the slot "
                         "and move to the waitlist.",
            "impact":    "Catches commitment drop-off early enough to fill the slot with another patient.",
            "agent":     "Reminder Agent",
        })

    # ── 4. Day-of-week: Thu/Mon ───────────────────────────────────────────────
    noshow_by_day = descriptive.get("noshow_by_day", {})
    sorted_days   = sorted(noshow_by_day.items(), key=lambda x: x[1], reverse=True)
    if sorted_days:
        worst_day, worst_rate = sorted_days[0]
        best_day, best_rate   = sorted_days[-1]
        if worst_rate > best_rate * 1.5:
            recommendations.append({
                "priority":  4,
                "title":     f"Apply Dynamic Overbooking on {worst_day}s",
                "rationale": f"{worst_day} has the highest no-show rate at {worst_rate}%, "
                             f"vs {best_rate}% on {best_day}s. Prime slots on {worst_day}s "
                             f"are systematically underutilised.",
                "action":    f"Book 1 additional patient per 8-slot block on {worst_day}s. "
                             f"If attendance is full, the overflow patient is automatically "
                             f"moved to the next slot by the Waitlist Agent.",
                "impact":    f"Recovers 1–2 appointment slots per {worst_day} per provider.",
                "agent":     "Slot Optimiser Agent",
            })

    # ── 5. New patient on prime slots ─────────────────────────────────────────
    noshow_pt  = descriptive.get("noshow_by_patient_type", {})
    new_rate   = noshow_pt.get("New", 0)
    ret_rate   = noshow_pt.get("Returning", 0)
    slot_ns    = descriptive.get("noshow_by_slot_type", {})
    prime_rate = slot_ns.get("Prime Slot", 0)
    if new_rate > ret_rate and prime_rate > slot_ns.get("Non-Prime Slot", 0):
        recommendations.append({
            "priority":  5,
            "title":     "Protect Prime Slots for Returning Patients",
            "rationale": f"New patients have a {new_rate}% no-show rate vs {ret_rate}% for returning. "
                         f"Prime slots have a {prime_rate}% no-show rate. Combining them is "
                         f"the highest-risk combination in your data.",
            "action":    "Gate prime slot access: new patients are offered non-prime slots on first "
                         "booking. After one successful attendance, they are unlocked for prime slots.",
            "impact":    "Reduces prime slot waste. Better patient experience for loyal patients.",
            "agent":     "Slot Optimiser Agent",
        })

    # ── 6. Waitlist activation ────────────────────────────────────────────────
    total_gaps = kpis.get("no_shows", 0) + kpis.get("cancelled", 0) + kpis.get("late_cancels", 0)
    if total_gaps > 10:
        recommendations.append({
            "priority":  6,
            "title":     "Activate Real-Time Waitlist to Fill Gaps",
            "rationale": f"You had {total_gaps} empty slots this period from no-shows and cancellations. "
                         f"Same-day bookings have the lowest no-show rate ({near_rate}%) — "
                         f"meaning a filled waitlist slot is very likely to attend.",
            "action":    "When a cancellation is confirmed or no-show flagged, the Waitlist Agent "
                         "immediately contacts the next patient on the list via their preferred channel. "
                         "No human action required.",
            "impact":    f"Up to R{round(kpis.get('avg_fee',900) * total_gaps * 0.6):,.0f} "
                         f"potential revenue recovery per month.",
            "agent":     "Waitlist Agent",
        })

    # ── Agent actions (immediate things agents would do today) ────────────────
    high_risk_count = predictive.get("risk_distribution", {}).get("High Risk", 0)
    if high_risk_count > 0:
        agent_actions.append({
            "agent":  "Reminder Agent",
            "action": f"Send high-priority reminder sequence to {high_risk_count} high-risk appointments.",
            "timing": "Immediate",
        })
    if total_gaps > 0:
        agent_actions.append({
            "agent":  "Waitlist Agent",
            "action": f"Review {total_gaps} empty slots and initiate waitlist outreach.",
            "timing": "Next business day",
        })
    agent_actions.append({
        "agent":  "Slot Optimiser Agent",
        "action": "Run overnight schedule review and flag over/under-booked blocks.",
        "timing": "Nightly 22:00",
    })
    agent_actions.append({
        "agent":  "Insight Narrator Agent",
        "action": "Generate and distribute weekly performance summary to practice manager.",
        "timing": "Weekly Monday 07:00",
    })

    # ── Quick wins (can be done without the platform) ─────────────────────────
    quick_wins = [
        {
            "title":  "Call back the top 10 highest-risk patients this week",
            "effort": "Low",
            "impact": "High",
            "detail": "Use the High Risk table in the Predictive section to identify the 10 "
                      "appointments most likely to no-show. A quick phone call cuts risk dramatically.",
        },
        {
            "title":  "Stop putting new WhatsApp patients in prime slots",
            "effort": "Low",
            "impact": "Medium",
            "detail": "A simple policy change. No system needed. Reserve 08:00 and 13:00 blocks "
                      "for phone-booked and returning patients.",
        },
        {
            "title":  "Build a waiting list — even a WhatsApp group",
            "effort": "Low",
            "impact": "High",
            "detail": f"You had {total_gaps} unfilled slots this period. A basic waitlist of "
                      "10–15 patients means cancellations get filled within the hour.",
        },
    ]

    return {
        "recommendations": sorted(recommendations, key=lambda r: r["priority"]),
        "agent_actions":   agent_actions,
        "quick_wins":      quick_wins,
        "summary": {
            "total_recommendations": len(recommendations),
            "high_priority":         sum(1 for r in recommendations if r["priority"] <= 2),
            "total_agent_actions":   len(agent_actions),
        },
    }
