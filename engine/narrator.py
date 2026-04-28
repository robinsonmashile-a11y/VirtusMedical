"""
CadenceWorks — Built-in Narrator Engine
Generates plain-English summaries for every dashboard tab.
No API key needed. Works from the data directly.
Written so anyone can understand it — simple, clear, no jargon.
"""

from datetime import datetime


def _pct(val, total):
    if not total: return 0
    return round(val / total * 100, 1)

def _fmt(val, symbol="R"):
    if val >= 1_000_000: return f"{symbol}{val/1_000_000:.1f}M"
    if val >= 1_000:     return f"{symbol}{val/1_000:.0f}k"
    return f"{symbol}{val:,.0f}"


# ── DESCRIPTIVE ────────────────────────────────────────────────────────────────

def narrate_descriptive(desc, meta, currency="R"):
    kpis        = desc.get("kpis", {})
    total       = kpis.get("total_appointments", 0)
    ns_rate     = kpis.get("no_show_rate", 0)
    rev_lost    = kpis.get("revenue_lost", 0)
    comp_rate   = kpis.get("completion_rate", 0)
    by_day      = desc.get("noshow_by_day", {})
    by_ch       = desc.get("noshow_by_channel", {})
    by_lead     = desc.get("noshow_by_lead_time", {})

    worst_day = max(by_day, key=lambda k: by_day[k]) if by_day else None
    worst_ch  = max(by_ch,  key=lambda k: by_ch[k])  if by_ch  else None
    best_day  = min(by_day, key=lambda k: by_day[k]) if by_day else None

    # Headline
    if ns_rate >= 12:
        headline = f"🚨 {ns_rate}% of patients are not showing up — that's a serious problem."
    elif ns_rate >= 8:
        headline = f"⚠️ {ns_rate}% of patients are not showing up — above the 8% danger zone."
    else:
        headline = f"✅ {ns_rate}% no-show rate — you're doing better than most practices."

    lines = [headline, ""]

    lines.append(
        f"Out of {total:,} appointments, {_fmt(rev_lost, currency)} was lost because "
        f"patients didn't come in. That money is gone — but it doesn't have to keep happening."
    )

    if worst_day:
        lines.append(
            f"The worst day is **{worst_day}** — {by_day[worst_day]}% of patients skip their appointment on that day. "
            + (f"**{best_day}** is your best day at {by_day[best_day]}%." if best_day else "")
        )

    if worst_ch:
        lines.append(
            f"Patients who book via **{worst_ch}** are most likely to not show up ({by_ch[worst_ch]}%). "
            f"This tells you where to focus your reminder efforts."
        )

    lead_15 = by_lead.get("15+ days", 0)
    lead_03 = by_lead.get("0–3 days", 0)
    if lead_15 and lead_03:
        lines.append(
            f"When patients book **more than 2 weeks in advance**, {lead_15}% don't show up — "
            f"compared to only {lead_03}% for same-week bookings. "
            f"The longer the wait, the more likely they forget."
        )

    lines.append(
        f"**Bottom line:** {comp_rate}% of your patients do show up. "
        f"Small improvements in reminders could recover {_fmt(rev_lost * 0.3, currency)}–{_fmt(rev_lost * 0.5, currency)} per month."
    )

    return "\n\n".join(lines)


# ── PREDICTIVE ─────────────────────────────────────────────────────────────────

def narrate_predictive(pred, desc, currency="R"):
    dist     = pred.get("risk_distribution", {})
    high     = dist.get("High Risk", 0)
    med      = dist.get("Medium Risk", 0)
    low      = dist.get("Low Risk", 0)
    total    = high + med + low
    kpis     = desc.get("kpis", {})
    rev_lost = kpis.get("revenue_lost", 0)
    avg_fee  = kpis.get("avg_fee", 500)

    high_rev_at_risk = high * avg_fee

    lines = []

    lines.append(
        f"Every appointment now has a **risk score from 0 to 100**. "
        f"Think of it like a weather forecast — the higher the number, the more likely that patient won't show up."
    )

    lines.append(
        f"Right now: **{high} appointments are High Risk** 🔴, "
        f"**{med} are Medium Risk** 🟠, and **{low} are Low Risk** 🟢. "
        f"That's {_pct(high, total)}% of your bookings that need attention."
    )

    if high_rev_at_risk > 0:
        lines.append(
            f"The {high} high-risk appointments represent about **{_fmt(high_rev_at_risk, currency)} in revenue** "
            f"that could walk out the door. A reminder sent today could save most of it."
        )

    lines.append(
        f"The model looks at things like: Is it a new patient? Did they book weeks in advance? "
        f"Is it a Monday morning or late afternoon slot? These are the patterns that predict no-shows."
    )

    lines.append(
        f"**What to do:** Focus your energy on the 🔴 High Risk patients first. "
        f"Send them a reminder today — don't wait until the day before."
    )

    return "\n\n".join(lines)


# ── PRESCRIPTIVE ───────────────────────────────────────────────────────────────

def narrate_prescriptive(presc, desc, currency="R"):
    recs     = presc.get("recommendations", [])
    kpis     = desc.get("kpis", {})
    rev_lost = kpis.get("revenue_lost", 0)
    ns_rate  = kpis.get("no_show_rate", 0)

    lines = []

    lines.append(
        f"This is your **action plan** — not just numbers, but exactly what to do next. "
        f"The engine looked at your data and came up with {len(recs)} specific steps to reduce no-shows."
    )

    if recs:
        top = recs[0]
        lines.append(
            f"**Most important action right now:** {top.get('title', '')}. "
            f"{top.get('rationale', '')} "
            f"{top.get('impact', '')}"
        )

    if len(recs) > 1:
        other_titles = [r.get("title", "") for r in recs[1:3]]
        lines.append(
            f"After that, focus on: **{' and '.join(other_titles)}**. "
            f"These are ranked by the impact they'll have on your revenue."
        )

    recovery_est = _fmt(rev_lost * 0.4, currency)
    lines.append(
        f"If you follow the top 3 recommendations, you could realistically recover "
        f"around **{recovery_est} per month** — that's money already being lost that you can get back."
    )

    lines.append(
        f"**Think of this tab as your to-do list.** Pick one action, do it today, and come back next week to see the difference."
    )

    return "\n\n".join(lines)


# ── ENRICHMENT ─────────────────────────────────────────────────────────────────

def narrate_enrichment(holiday_analysis, weather_analysis, upcoming_hols):
    lines = []

    lines.append(
        f"This section adds **extra context** to your booking data — things outside your control "
        f"that still affect whether patients show up."
    )

    # Holiday
    if holiday_analysis:
        worst   = holiday_analysis.get("worst_period", "holiday periods")
        impact  = holiday_analysis.get("holiday_impact_score", 0)
        rev_risk = holiday_analysis.get("revenue_at_risk", 0)
        lines.append(
            f"🗓 **Public Holidays:** Patients are **{impact}% more likely** to skip appointments "
            f"around public holidays. The worst time is **{worst}**. "
            f"This puts about **R{rev_risk:,.0f} in revenue at risk** every holiday period."
        )
        if upcoming_hols:
            next_hol = upcoming_hols[0]
            lines.append(
                f"📅 **Coming up:** {next_hol['name']} is in **{next_hol['days_until']} days** ({next_hol['date']}). "
                f"Start sending extra reminders to patients booked around that date now."
            )
    else:
        lines.append(
            f"🗓 **Public Holidays:** Turn on the holiday toggle in the sidebar to see how SA public holidays "
            f"affect your no-show rates. It usually makes a big difference."
        )

    # Weather
    if weather_analysis:
        uplift = weather_analysis.get("rain_uplift", 0)
        sig    = weather_analysis.get("weather_is_significant", False)
        if sig:
            lines.append(
                f"🌧 **Weather:** On rainy days, your no-show rate goes up by **{uplift}%**. "
                f"When the southeaster is blowing or it's cold, patients are more likely to stay home. "
                f"The system will flag upcoming bad weather days so you can send extra reminders."
            )
        else:
            lines.append(
                f"🌤 **Weather:** Weather doesn't seem to affect your patients much right now (less than 2% difference). "
                f"We'll keep watching."
            )
    else:
        lines.append(
            f"🌦 **Weather:** Turn on the weather toggle in the sidebar to see if Cape Town weather "
            f"affects your no-show rates. Requires internet."
        )

    lines.append(
        f"**Why this matters:** Knowing that a public holiday is coming lets you send reminders "
        f"earlier. Knowing it's going to rain lets you follow up with a quick call. "
        f"Small actions at the right time = fewer empty chairs."
    )

    return "\n\n".join(lines)


# ── SCORE NEW BOOKINGS ─────────────────────────────────────────────────────────

def narrate_score_new_bookings(stats):
    total  = stats.get("total", 0)
    high   = stats.get("high_risk", 0)
    medium = stats.get("medium_risk", 0)
    rev    = stats.get("revenue_at_risk", 0)

    lines = []

    if total == 0:
        return (
            "📂 **No bookings yet.** Upload a file or add a booking manually above. "
            "Every booking you add here gets a risk score instantly and shows up in "
            "Live Monitor and Reminder Agent automatically."
        )

    lines.append(
        f"You have **{total} bookings** loaded. Each one has been given a risk score "
        f"— a number from 0 to 100 that tells you how likely that patient is to not show up."
    )

    if high > 0:
        lines.append(
            f"🔴 **{high} bookings are High Risk** — these patients need a reminder as soon as possible. "
            f"They represent about **R{rev:,.0f}** that could be lost."
        )

    if medium > 0:
        lines.append(
            f"🟠 **{medium} bookings are Medium Risk** — worth a reminder, but not as urgent."
        )

    lines.append(
        f"These bookings are now shared with **Live Monitor** (to keep an eye on them) "
        f"and **Reminder Agent** (to send reminders automatically). You don't need to do anything else."
    )

    return "\n\n".join(lines)


# ── LIVE MONITOR ───────────────────────────────────────────────────────────────

def narrate_live_monitor(stats):
    total    = stats.get("total", 0)
    high     = stats.get("high_risk", 0)
    pending  = stats.get("pending_reminders", 0)
    rev      = stats.get("revenue_at_risk", 0)

    lines = []

    if total == 0:
        return (
            "📭 **Nothing to monitor yet.** Go to Score New Bookings and upload your upcoming appointments. "
            "They'll appear here instantly."
        )

    lines.append(
        f"This is your **live view** of all upcoming appointments — updated the moment a new booking is added. "
        f"Think of it like a control room for your schedule."
    )

    if high > 0:
        lines.append(
            f"🔴 **{high} high-risk patients** need attention right now. "
            f"These are the ones most likely to not show up, and they represent "
            f"**R{rev:,.0f}** in revenue at risk."
        )

    if pending > 0:
        lines.append(
            f"⏰ **{pending} reminders haven't been sent yet.** "
            f"Head to Reminder Agent to send them — or schedule them to go out automatically."
        )

    lines.append(
        f"Use the filters at the top to focus on just the High Risk patients, "
        f"or search for a specific patient by name. "
        f"Once a reminder is sent, it shows ✓ Reminded in the table."
    )

    return "\n\n".join(lines)


# ── REMINDER AGENT ─────────────────────────────────────────────────────────────

def narrate_reminder_agent(r_stats, pending_count, twilio_ok):
    queued = r_stats.get("queued", 0)
    sent   = r_stats.get("sent", 0)
    live   = r_stats.get("live_sent", 0)

    lines = []

    mode = "🟢 **Live mode** — real WhatsApp messages are being sent." if twilio_ok else \
           "🟡 **Dry run mode** — messages are previewed but not sent yet. Add Twilio to go live."

    lines.append(
        f"This is your **automated reminder system**. It reads the high-risk bookings "
        f"from the shared database and sends WhatsApp reminders at the right time — "
        f"48 hours before and 2 hours before for high-risk patients. {mode}"
    )

    if pending_count > 0:
        lines.append(
            f"📋 **{pending_count} patients are waiting for reminders.** "
            f"Click 'Schedule All Reminders' to queue them up, or 'Run Agent Now' to send immediately."
        )
    else:
        lines.append(
            f"✅ **No reminders pending right now.** Add bookings in Score New Bookings "
            f"and they'll appear here automatically when reminders are due."
        )

    if sent > 0 or live > 0:
        lines.append(
            f"So far: **{sent} reminders sent** ({live} live WhatsApp messages delivered). "
            f"Every reminder sent is a patient who's less likely to forget their appointment."
        )

    lines.append(
        f"**How it works:** High-risk patients get 2 reminders — one 2 days before, one 2 hours before. "
        f"Medium-risk patients get 1 reminder 2 days before. Low-risk patients are left alone. "
        f"Simple, targeted, effective."
    )

    return "\n\n".join(lines)


# ── MASTER SUMMARY ─────────────────────────────────────────────────────────────

def narrate_overview(desc, pred, presc, currency="R"):
    """One short paragraph shown at the very top of the dashboard."""
    kpis     = desc.get("kpis", {})
    total    = kpis.get("total_appointments", 0)
    ns_rate  = kpis.get("no_show_rate", 0)
    rev_lost = kpis.get("revenue_lost", 0)
    dist     = pred.get("risk_distribution", {})
    high     = dist.get("High Risk", 0)
    recs     = presc.get("recommendations", [])
    top_action = recs[0].get("title", "send targeted reminders") if recs else "send targeted reminders"

    emoji = "🚨" if ns_rate >= 12 else "⚠️" if ns_rate >= 8 else "✅"

    return (
        f"{emoji} Out of **{total:,} appointments**, **{ns_rate}%** of patients didn't show up — "
        f"costing **{_fmt(rev_lost, currency)}** in lost revenue. "
        f"Right now **{high} upcoming bookings** are flagged as high risk. "
        f"The single most important thing to do today: **{top_action}**."
    )
