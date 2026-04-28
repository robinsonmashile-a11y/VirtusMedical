"""
CadenceWorks Analytics Engine
Streamlit App — run with: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))
from engine import ingestor, descriptive, predictive, prescriptive
from engine import live_sync
from engine import reminder_agent
from engine import holiday_enrichment
from engine import weather_enrichment
from engine import client_ingestor
from engine import narrator
from engine import inbox as inbox_engine
from engine import review_agent
from engine import voice_engine
from engine import proof_report

# ── Init live DB
live_sync.init_db()
reminder_agent.init_reminder_tables()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Virtus Health — CadenceWorks Demo",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Brand CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');

  :root {
    --navy: #1a3c4d;
    --teal: #3dbfaa;
    --teal-dk: #2ea393;
    --teal-lt: #e8f8f5;
    --amber: #e8923a;
    --amber-lt: #fdf5ed;
    --green: #2ea37a;
    --green-lt: #edf7f3;
    --red: #e05252;
    --red-lt: #fdf0f0;
    --muted: #6b8899;
    --border: #e0e6ea;
  }

  /* Global font */
  html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
  }

  /* Hide default Streamlit chrome */
  #MainMenu, footer, header { visibility: hidden; }
  .block-container { padding-top: 0rem !important; padding-bottom: 2rem; }

  /* Sidebar */
  [data-testid="stSidebar"] {
    background: #1a3c4d !important;
  }
  [data-testid="stSidebar"] * {
    color: rgba(255,255,255,0.85) !important;
  }
  [data-testid="stSidebar"] .stMarkdown h1,
  [data-testid="stSidebar"] .stMarkdown h2,
  [data-testid="stSidebar"] .stMarkdown h3 {
    color: #fff !important;
  }
  [data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.15) !important;
  }

  /* Upload area */
  [data-testid="stFileUploader"] {
    background: var(--teal-lt);
    border: 2px dashed var(--teal) !important;
    border-radius: 12px;
    padding: 12px;
  }

  /* Metric cards */
  [data-testid="metric-container"] {
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 16px 20px !important;
    box-shadow: 0 2px 12px rgba(26,60,77,0.08);
  }
  [data-testid="stMetricLabel"] {
    font-size: 11px !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--muted) !important;
  }
  [data-testid="stMetricValue"] {
    font-size: 28px !important;
    font-weight: 800 !important;
    color: var(--navy) !important;
  }

  /* Tabs */
  .stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: transparent;
    border-bottom: 2px solid var(--border);
  }
  .stTabs [data-baseweb="tab"] {
    background: transparent;
    border-radius: 8px 8px 0 0;
    font-weight: 600;
    font-size: 13px;
    color: var(--muted);
    padding: 8px 20px;
  }
  .stTabs [aria-selected="true"] {
    background: var(--teal-lt) !important;
    color: var(--teal-dk) !important;
    border-bottom: 2px solid var(--teal) !important;
  }

  /* Tables */
  [data-testid="stTable"] table {
    border-collapse: collapse;
    width: 100%;
  }
  [data-testid="stTable"] th {
    background: #f0f2f5;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--muted);
    padding: 10px 12px;
  }
  [data-testid="stTable"] td {
    font-size: 13px;
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
  }

  /* Cards via markdown */
  .cw-card {
    background: #fff;
    border: 1px solid #e0e6ea;
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 14px;
    box-shadow: 0 2px 12px rgba(26,60,77,0.08);
  }
  .cw-hero {
    background: linear-gradient(135deg, #1a3c4d 0%, #1e4f66 60%, #24607a 100%);
    border-radius: 16px;
    padding: 36px 40px;
    margin-bottom: 24px;
    color: white;
  }
  .cw-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
  }
  .badge-teal  { background: #e8f8f5; color: #2ea393; }
  .badge-red   { background: #fdf0f0; color: #e05252; }
  .badge-amber { background: #fdf5ed; color: #e8923a; }
  .badge-green { background: #edf7f3; color: #2ea37a; }
  .badge-navy  { background: #eaf0f3; color: #1a3c4d; }

  .rx-card {
    background: #fff;
    border: 1px solid #e0e6ea;
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 12px;
    border-left: 4px solid #3dbfaa;
    box-shadow: 0 2px 8px rgba(26,60,77,0.06);
  }
  .rx-card.high { border-left-color: #e05252; }
  .rx-card.med  { border-left-color: #e8923a; }

  .agent-card {
    background: #fff;
    border: 1px solid #e0e6ea;
    border-top: 3px solid #e8923a;
    border-radius: 12px;
    padding: 16px 18px;
    box-shadow: 0 2px 8px rgba(26,60,77,0.06);
  }

  .risk-high { color: #e05252; font-weight: 700; }
  .risk-med  { color: #e8923a; font-weight: 700; }
  .risk-low  { color: #2ea37a; font-weight: 700; }

  /* Section headers */
  .section-pill {
    display: inline-block;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 16px;
  }

  /* Progress bars */
  .stProgress > div > div {
    background: var(--teal) !important;
    border-radius: 99px;
  }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='padding: 8px 0 20px 0'>
      <div style='display:flex; align-items:center; gap:10px; margin-bottom:6px'>
        <svg width='32' height='32' viewBox='0 0 40 40' fill='none'>
          <rect width='40' height='40' rx='8' fill='rgba(61,191,170,0.2)'/>
          <polyline points='4,28 10,18 16,22 22,10 28,16 36,6'
            stroke='#3dbfaa' stroke-width='2.5'
            stroke-linecap='round' stroke-linejoin='round' fill='none'/>
          <circle cx='22' cy='10' r='2.5' fill='white'/>
        </svg>
        <span style='font-size:18px; font-weight:800; color:white'>CadenceWorks</span>
      </div>
      <div style='font-size:11px; color:rgba(255,255,255,0.45); letter-spacing:1px; text-transform:uppercase'>
        Virtus Health Demo
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("""
    <div style='background:rgba(61,191,170,0.12);border:1px solid rgba(61,191,170,0.25);
                border-radius:10px;padding:12px 14px;font-size:12px;color:rgba(255,255,255,0.75);
                line-height:1.6'>
      📊 <strong style='color:#3dbfaa'>Virtus Health Demo</strong><br>
      Modelled data · Oct 2024 – Mar 2025<br>
      5 doctors · 5 service pillars · 420 appointments
    </div>""", unsafe_allow_html=True)

    # Demo mode — no upload, no settings exposed
    uploaded_file   = None
    uploaded_type   = None
    uploaded_status = None
    currency_symbol   = "R"
    no_show_threshold = 8
    anthropic_api_key = ""
    enrich_holidays   = True
    enrich_weather    = False
    upload_mode       = "Single file"

    st.markdown("---")
    st.markdown("### 🌍 Enrichment")
    enrich_holidays = st.toggle("Public Holidays (SA)", value=True,
        help="Flags SA public holidays and school breaks. No internet required.")
    enrich_weather  = st.toggle("Weather (Cape Town)", value=False,
        help="Fetches historical weather from Open-Meteo. Requires internet.")

    st.markdown("---")
    st.markdown("""
    <div style='font-size:11px; color:rgba(255,255,255,0.4); line-height:1.8'>
      <strong style='color:rgba(255,255,255,0.7)'>How it works</strong><br>
      1. Upload any booking Excel/CSV<br>
      2. Engine auto-maps your columns<br>
      3. Runs descriptive, predictive<br>
         &amp; prescriptive analytics<br>
      4. Explore results in each tab
    </div>
    """, unsafe_allow_html=True)


# ── Helper functions ──────────────────────────────────────────────────────────
def fmt_currency(val, symbol=None):
    s = symbol or currency_symbol
    if val >= 1_000_000: return f"{s}{val/1_000_000:.1f}M"
    if val >= 1_000:     return f"{s}{val/1_000:.0f}k"
    return f"{s}{val:,.0f}"

def risk_badge(score):
    if score >= 20:  return f'<span class="cw-badge badge-red">High Risk · {score}</span>'
    if score >= 12:  return f'<span class="cw-badge badge-amber">Medium Risk · {score}</span>'
    return f'<span class="cw-badge badge-green">Low Risk · {score}</span>'

def bar_html(label, val, max_val, color="teal", suffix="%"):
    pct = round(val / max_val * 100) if max_val else 0
    colors = {"teal": "#3dbfaa", "red": "#e05252", "amber": "#e8923a", "navy": "#1a3c4d", "green": "#2ea37a"}
    c = colors.get(color, "#3dbfaa")
    return f"""
    <div style='display:flex;align-items:center;gap:10px;margin-bottom:10px;font-size:13px'>
      <span style='width:110px;flex-shrink:0;color:#6b8899;font-weight:500'>{label}</span>
      <div style='flex:1;height:8px;background:#f0f2f5;border-radius:99px;overflow:hidden'>
        <div style='width:{pct}%;height:100%;background:{c};border-radius:99px'></div>
      </div>
      <span style='width:52px;text-align:right;font-weight:700;color:#1a3c4d'>{val}{suffix}</span>
    </div>"""

def noshow_color(val, lo=8, hi=15):
    if val >= hi: return "red"
    if val >= lo: return "amber"
    return "teal"


# ── AI Narrator function ──────────────────────────────────────────────────────
def generate_narrative(kpis, desc, pred, presc, api_key, currency="R"):
    """Call Anthropic API to generate plain-English narrative from analytics data."""
    import urllib.request, json

    noshow_by_day  = desc.get("noshow_by_day", {})
    noshow_by_ch   = desc.get("noshow_by_channel", {})
    noshow_by_lead = desc.get("noshow_by_lead_time", {})
    top_rec        = presc.get("recommendations", [{}])[0]
    risk_dist      = pred.get("risk_distribution", {})
    try:
        worst_day = max(noshow_by_day, key=lambda k: float(noshow_by_day[k]) if not isinstance(noshow_by_day[k], dict) else 0) if noshow_by_day else "unknown"
    except Exception:
        worst_day = next(iter(noshow_by_day), "unknown")
    try:
        worst_ch = max(noshow_by_ch, key=lambda k: float(noshow_by_ch[k]) if not isinstance(noshow_by_ch[k], dict) else 0) if noshow_by_ch else "unknown"
    except Exception:
        worst_ch = next(iter(noshow_by_ch), "unknown")

    prompt = f"""You are the Insight Narrator for CadenceWorks, an AI analytics platform for medical practices.
You have just analysed booking data for Virtus Health & Medical — a premium multi-doctor GP practice in Sea Point, Cape Town 
with 4 service pillars: Health, Aesthetics, Longevity, and Sports Medicine.
Write a concise, sharp, plain-English executive summary in exactly 3 short paragraphs. 
No bullet points. No headers. No markdown. Just direct, confident prose.

DATA:
- Total appointments: {kpis.get("total_appointments")}
- Completion rate: {kpis.get("completion_rate")}%
- No-show rate: {kpis.get("no_show_rate")}% (industry threshold: 8%)
- Revenue lost to no-shows: {currency}{kpis.get("revenue_lost", 0):,.0f}
- Avg lead time: {kpis.get("avg_lead_time_days")} days
- Worst no-show day: {worst_day} ({noshow_by_day.get(worst_day, 0)}%)
- Worst channel: {worst_ch} ({noshow_by_ch.get(worst_ch, 0)}%)
- No-show rate for 15+ day bookings: {noshow_by_lead.get("15+ days", 0)}%
- No-show rate for 0-3 day bookings: {noshow_by_lead.get("0–3 days", 0)}%
- High risk appointments: {risk_dist.get("High Risk", 0)}
- Top recommendation: {top_rec.get("title", "")}

PARAGRAPH 1: State the single biggest operational problem revealed by this data. Be specific — use the actual numbers. Reference Virtus Health's 5 service pillars where relevant (General Health & Wellness, Virtus Infusion Clinic, Virtus Baby Clinic, Virtus Aesthetics Clinic, Woman Wellness).

PARAGRAPH 2: Explain the root cause in plain language. Why is this happening? What does the data suggest about patient behaviour or booking patterns at a premium practice like this?

PARAGRAPH 3: State the single most important action Virtus Health should take this week. Be direct and specific. End with the estimated financial impact in rands.

Write as if you are a sharp analyst briefing Dr Ryan Jankelowitz and Dr Jane Benjamin over coffee. Confident, clear, no fluff."""

    payload = json.dumps({{
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 500,
        "messages": [{{"role": "user", "content": prompt}}]
    }}).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={{
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
    return result["content"][0]["text"]



def narrator_box(text, color="#3dbfaa"):
    import re
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    lines = html.split("\n\n")
    paras = "".join(f"<p style='margin:0 0 12px 0;line-height:1.8;font-size:13px;color:#1a3c4d'>{p}</p>" for p in lines if p.strip())
    st.markdown(f"""
    <div style='background:#f8fafb;border-left:3px solid {color};border-radius:0 10px 10px 0;
                padding:16px 20px;margin-bottom:20px'>
      <div style='font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;
                  color:{color};margin-bottom:8px'>⬡ What this means</div>
      {paras}
    </div>""", unsafe_allow_html=True)

def section_header(pill_text, title, pill_color="#3dbfaa"):
    st.markdown(f"""
    <div style='display:flex;align-items:center;gap:14px;margin-bottom:20px;margin-top:8px'>
      <span class='section-pill' style='background:{pill_color};color:white'>{pill_text}</span>
      <span style='font-size:20px;font-weight:700;color:#1a3c4d'>{title}</span>
    </div>""", unsafe_allow_html=True)


# ── Demo mode — auto-load Virtus Health data ─────────────────────────────────
_two_ready    = False
_single_ready = False


# ── Run pipeline ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def run_pipeline(file_bytes, file_name, do_holidays=True, do_weather=False):
    import tempfile, os
    suffix = Path(file_name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        df, meta = ingestor.ingest(tmp_path)

        # Enrichment
        holiday_analysis = {}
        weather_analysis = {}
        weather_forecast = []
        upcoming_hols    = []

        if do_holidays:
            try:
                df = holiday_enrichment.enrich(df)
                holiday_analysis = holiday_enrichment.holiday_noshow_analysis(df)
                upcoming_hols    = holiday_enrichment.get_upcoming_holidays(days_ahead=60)
            except Exception as e:
                print(f"  [holiday] error: {e}")

        if do_weather:
            try:
                df = weather_enrichment.enrich(df)
                weather_analysis = weather_enrichment.analyse(df)
                weather_forecast = weather_enrichment.get_forecast(days_ahead=7)
            except Exception as e:
                print(f"  [weather] error: {e}")

        desc  = descriptive.run(df)
        pred  = predictive.run(df)
        presc = prescriptive.run(df, desc, pred)
        return df, meta, desc, pred, presc, holiday_analysis, weather_analysis, weather_forecast, upcoming_hols
    finally:
        os.unlink(tmp_path)

@st.cache_data(show_spinner=False)
def run_pipeline_two(type_bytes, type_name, status_bytes, status_name, do_holidays=True, do_weather=False):
    import tempfile, os
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(type_name).suffix) as t1:
        t1.write(type_bytes); p1 = t1.name
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(status_name).suffix) as t2:
        t2.write(status_bytes); p2 = t2.name
    try:
        df, meta = client_ingestor.ingest_two_file_for_engine(p1, p2)
        holiday_analysis, weather_analysis, weather_forecast, upcoming_hols = {}, {}, [], []
        if do_holidays:
            try:
                df = holiday_enrichment.enrich(df)
                holiday_analysis = holiday_enrichment.holiday_noshow_analysis(df)
                upcoming_hols    = holiday_enrichment.get_upcoming_holidays(days_ahead=60)
            except Exception as e:
                print(f"  [holiday] error: {e}")
        if do_weather:
            try:
                df = weather_enrichment.enrich(df)
                weather_analysis = weather_enrichment.analyse(df)
                weather_forecast = weather_enrichment.get_forecast(days_ahead=7)
            except Exception as e:
                print(f"  [weather] error: {e}")
        desc  = descriptive.run(df)
        pred  = predictive.run(df)
        presc = prescriptive.run(df, desc, pred)
        return df, meta, desc, pred, presc, holiday_analysis, weather_analysis, weather_forecast, upcoming_hols
    finally:
        os.unlink(p1); os.unlink(p2)


# ── Auto-load Virtus Health demo data ────────────────────────────────────────
_DEMO_FILE         = Path(__file__).parent / "VirtusHealth_Historical_Bookings.xlsx"
_NEW_BOOKINGS_FILE = Path(__file__).parent / "VirtusHealth_NewBookings_NextWeek.xlsx"

with st.spinner("🔄 Loading Virtus Health analytics..."):
    with open(_DEMO_FILE, "rb") as _f:
        _demo_bytes = _f.read()
    df, meta, desc, pred, presc, holiday_analysis, weather_analysis, weather_forecast, upcoming_hols = run_pipeline(
        _demo_bytes, "VirtusHealth_Historical_Bookings.xlsx",
        do_holidays=enrich_holidays, do_weather=enrich_weather,
    )

# ── Auto-ingest next week's bookings into Live Monitor (once per session) ─────
if "new_bookings_loaded" not in st.session_state:
    if _NEW_BOOKINGS_FILE.exists():
        try:
            with open(_NEW_BOOKINGS_FILE, "rb") as _f:
                _nb_bytes = _f.read()
            _nb_count = live_sync.ingest_bytes(_nb_bytes, "VirtusHealth_NewBookings_NextWeek.xlsx")
            st.session_state["new_bookings_loaded"] = _nb_count
        except Exception as _e:
            print(f"[demo] New bookings auto-ingest error: {_e}")
            st.session_state["new_bookings_loaded"] = 0

kpis = desc.get("kpis", {})
dr   = meta.get("date_range", ("—", "—"))


# ── Top hero strip ────────────────────────────────────────────────────────────
ns_rate = kpis.get("no_show_rate", 0)
alert_color = "#e05252" if ns_rate >= no_show_threshold else "#2ea37a"

st.markdown(f"""
<div style='background:linear-gradient(135deg,#1a3c4d 0%,#1e4f66 60%,#24607a 100%);
            border-radius:16px;padding:28px 36px;margin-bottom:24px;position:relative;overflow:hidden'>
  <div style='position:absolute;top:-60px;right:-60px;width:220px;height:220px;
              background:#3dbfaa;border-radius:50%;opacity:0.08'></div>
  <div style='font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;
              color:#3dbfaa;margin-bottom:8px'>● Operational Intelligence Report</div>
  <div style='font-size:22px;font-weight:800;color:white;margin-bottom:6px'>
    {meta.get("source_file","Uploaded File")}
  </div>
  <div style='font-size:13px;color:rgba(255,255,255,0.55)'>
    {dr[0]} to {dr[1]} &nbsp;·&nbsp; {kpis.get("total_appointments",0)} appointments
    &nbsp;·&nbsp; {", ".join(meta.get("providers",[]))}
    &nbsp;·&nbsp; <span style='color:{alert_color};font-weight:700'>No-show rate: {ns_rate}%</span>
  </div>
</div>
""", unsafe_allow_html=True)


# ── Built-in Narrator — overview strip ───────────────────────────────────────
_overview = narrator.narrate_overview(desc, pred, presc, currency=currency_symbol)
_overview_html = _overview.replace("**", "<strong>").replace("**", "</strong>")
import re as _re
_overview_html = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", _overview)
st.markdown(f"""
<div style='background:#fff;border:1px solid #e0e6ea;border-left:4px solid #3dbfaa;
            border-radius:0 14px 14px 0;padding:20px 28px;margin-bottom:24px;
            box-shadow:0 2px 12px rgba(26,60,77,0.06)'>
  <div style='font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;
              color:#3dbfaa;margin-bottom:8px'>⬡ CadenceWorks Summary</div>
  <div style='font-size:14px;color:#1a3c4d;line-height:1.8'>{_overview_html}</div>
</div>""", unsafe_allow_html=True)


# ── Tabs ──────────────────────────────────────────────────────────────────────
# All 8 tabs — analytics + operational
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12 = st.tabs([
    "📊  Descriptive",
    "🤖  Predictive",
    "🎯  Prescriptive",
    "🌍  Enrichment",
    "⚡  Score New Bookings",
    "🔴  Live Monitor",
    "💬  Reminder Agent",
    "💬  WhatsApp",
    "⭐  5-Star Builder",
    "🗣️  Patient Voice",
    "📄  Proof Report",
    "📸  Instagram Agent",
])

with tab1:
    narrator_box(narrator.narrate_descriptive(desc, meta, currency=currency_symbol), "#3dbfaa")
    section_header("01 · Descriptive", "What is currently happening")

    # KPI row
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Appointments",  kpis.get("total_appointments", 0))
    c2.metric("Completion Rate",     f"{kpis.get('completion_rate', 0)}%")
    c3.metric("No-Show Rate",        f"{kpis.get('no_show_rate', 0)}%",
              delta=f"{kpis.get('no_show_rate',0) - no_show_threshold:.1f}% vs threshold",
              delta_color="inverse")
    c4.metric("Cancellation Rate",   f"{kpis.get('cancellation_rate', 0)}%")
    c5.metric("Revenue at Risk",     fmt_currency(kpis.get("revenue_lost", 0)))
    c6.metric("Avg Lead Time",       f"{kpis.get('avg_lead_time_days', 0)}d")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # Row 1: Channel + Lead Time
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("<div class='cw-card'>", unsafe_allow_html=True)
        st.markdown("**No-Show Rate by Booking Channel**")
        ch_data = desc.get("noshow_by_channel", {})
        max_v = max(ch_data.values()) if ch_data else 1
        bars = "".join(bar_html(k, v, max_v, noshow_color(v)) for k, v in ch_data.items())
        st.markdown(bars, unsafe_allow_html=True)
        if "WhatsApp" in ch_data:
            wa = ch_data["WhatsApp"]
            ph = ch_data.get("Phone", 1)
            st.markdown(f"""<div style='background:#fdf5ed;border-left:3px solid #e8923a;
                border-radius:0 8px 8px 0;padding:10px 14px;font-size:12px;color:#7a4f1a;margin-top:12px'>
                WhatsApp no-show rate is <strong>{round(wa/ph,1)}× higher</strong> than phone bookings.</div>""",
                unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown("<div class='cw-card'>", unsafe_allow_html=True)
        st.markdown("**No-Show Rate by Lead Time**")
        ld_data = desc.get("noshow_by_lead_time", {})
        max_v = max(ld_data.values()) if ld_data else 1
        bars = "".join(bar_html(k, v, max_v, noshow_color(v, 8, 18)) for k, v in ld_data.items())
        st.markdown(bars, unsafe_allow_html=True)
        far = ld_data.get("15+ days", 0)
        near = ld_data.get("0–3 days", 1)
        if far and near:
            st.markdown(f"""<div style='background:#e8f8f5;border-left:3px solid #3dbfaa;
                border-radius:0 8px 8px 0;padding:10px 14px;font-size:12px;color:#2a5f52;margin-top:12px'>
                15+ day bookings are <strong>{round(far/near,1)}× more likely</strong> to no-show than same-week bookings.</div>""",
                unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Row 2: Day of week + Patient/Slot type
    col3, col4 = st.columns(2)

    with col3:
        st.markdown("<div class='cw-card'>", unsafe_allow_html=True)
        st.markdown("**No-Show Rate by Day of Week**")
        day_data = desc.get("noshow_by_day", {})
        max_v = max(day_data.values()) if day_data else 1
        bars = "".join(bar_html(k, v, max_v, noshow_color(v, 10, 18)) for k, v in day_data.items())
        st.markdown(bars, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col4:
        st.markdown("<div class='cw-card'>", unsafe_allow_html=True)
        st.markdown("**No-Show by Patient Type & Slot Priority**")
        pt_data = desc.get("noshow_by_patient_type", {})
        sl_data = desc.get("noshow_by_slot_type", {})
        all_data = {**pt_data, **sl_data}
        max_v = max(all_data.values()) if all_data else 1
        bars = "".join(bar_html(k, v, max_v, noshow_color(v)) for k, v in all_data.items())
        st.markdown(bars, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Provider comparison table
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    prov = desc.get("provider_comparison", [])
    if prov:
        st.markdown("**Provider Performance Comparison**")
        prov_df = pd.DataFrame(prov).rename(columns={
            "provider": "Provider", "total": "Total", "completed": "Completed",
            "no_show_rate": "No-Show Rate (%)", "revenue": "Revenue",
            "avg_lead": "Avg Lead (days)"
        })
        prov_df["Revenue"] = prov_df["Revenue"].apply(lambda x: fmt_currency(x))
        st.dataframe(prov_df, use_container_width=True, hide_index=True)

    # Status breakdown
    col5, col6 = st.columns(2)
    with col5:
        vol_status = desc.get("volume_by_status", {})
        if vol_status:
            st.markdown("**Appointment Status Breakdown**")
            st.bar_chart(pd.Series(vol_status), use_container_width=True, height=200)
    with col6:
        vol_appt = desc.get("volume_by_appt_type", {})
        if vol_appt:
            st.markdown("**Volume by Appointment Type**")
            st.bar_chart(pd.Series(vol_appt), use_container_width=True, height=200)

    # Pillar breakdown (Virtus Health)
    vol_pillar = desc.get("volume_by_pillar", {})
    ns_pillar  = desc.get("noshow_by_pillar", {})
    rev_pillar = desc.get("revenue_by_pillar", {})
    lost_pillar = desc.get("lost_revenue_by_pillar", {})
    if vol_pillar:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown("**Performance by Service Pillar**")
        pillar_rows = []
        for p in vol_pillar:
            pillar_rows.append({
                "Pillar":           p,
                "Appointments":     vol_pillar.get(p, 0),
                "No-Show Rate (%)": ns_pillar.get(p, 0),
                "Revenue (R)":      fmt_currency(rev_pillar.get(p, 0)),
                "Lost to No-Shows": fmt_currency(lost_pillar.get(p, 0)),
            })
        st.dataframe(pd.DataFrame(pillar_rows), use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — PREDICTIVE
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    narrator_box(narrator.narrate_predictive(pred, desc, currency=currency_symbol), "#1a3c4d")
    section_header("02 · Predictive", "Who will no-show — AI risk scoring", "#1a3c4d")

    # Model info banner
    model_type = pred.get("model_type", "—")
    auc        = pred.get("model_auc")
    auc_str    = f"AUC: {auc}" if auc else "Rule-Based Scoring"
    st.markdown(f"""
    <div style='background:#1a3c4d;border-radius:14px;padding:24px 28px;margin-bottom:24px'>
      <div style='font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;
                  color:#3dbfaa;margin-bottom:8px'>⬡ Model Active</div>
      <div style='font-size:15px;color:rgba(255,255,255,0.8);line-height:1.7;max-width:700px'>
        Every appointment has been scored <strong style='color:white'>0–100</strong> for no-show probability
        using <strong style='color:white'>{model_type}</strong>.
        The model uses lead time, channel, patient type, day of week, slot priority and appointment type.
        <span style='background:rgba(61,191,170,0.2);color:#3dbfaa;padding:2px 10px;
              border-radius:20px;font-size:12px;font-weight:700;margin-left:8px'>{auc_str}</span>
      </div>
    </div>""", unsafe_allow_html=True)

    # Risk band cards
    risk_dist = pred.get("risk_distribution", {})
    total_apts = kpis.get("total_appointments", 1)

    rc1, rc2, rc3 = st.columns(3)
    high = risk_dist.get("High Risk", 0)
    med  = risk_dist.get("Medium Risk", 0)
    low  = risk_dist.get("Low Risk", 0)
    rc1.metric("🔴 High Risk",   high, f"{round(high/total_apts*100)}% of appointments")
    rc2.metric("🟠 Medium Risk", med,  f"{round(med/total_apts*100)}% of appointments")
    rc3.metric("🟢 Low Risk",    low,  f"{round(low/total_apts*100)}% of appointments")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("<div class='cw-card'>", unsafe_allow_html=True)
        st.markdown("**Feature Importance — What drives the risk score**")
        fi = pred.get("feature_importance", {})
        max_v = max(fi.values()) if fi else 1
        bars = "".join(
            bar_html(k.replace("_", " ").title(), round(v * 100), round(max_v * 100), "teal", "%")
            for k, v in list(fi.items())[:7]
        )
        st.markdown(bars, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown("<div class='cw-card'>", unsafe_allow_html=True)
        st.markdown("**Model Validation**")
        val = pred.get("validation", {})
        ss  = pred.get("score_stats", {})
        st.markdown(f"""
        <table width='100%' style='font-size:13px;border-collapse:collapse'>
          <tr style='border-bottom:1px solid #e0e6ea'>
            <td style='padding:8px 4px;color:#6b8899'>Actual no-shows</td>
            <td style='padding:8px 4px;font-weight:700;text-align:right'>{val.get('actual_no_shows','—')} ({val.get('actual_rate_pct','—')}%)</td>
          </tr>
          <tr style='border-bottom:1px solid #e0e6ea'>
            <td style='padding:8px 4px;color:#6b8899'>Predicted high-risk</td>
            <td style='padding:8px 4px;font-weight:700;text-align:right'>{val.get('predicted_high_risk','—')}</td>
          </tr>
          <tr style='border-bottom:1px solid #e0e6ea'>
            <td style='padding:8px 4px;color:#6b8899'>Mean risk score</td>
            <td style='padding:8px 4px;font-weight:700;text-align:right'>{ss.get('mean','—')}</td>
          </tr>
          <tr style='border-bottom:1px solid #e0e6ea'>
            <td style='padding:8px 4px;color:#6b8899'>Median risk score</td>
            <td style='padding:8px 4px;font-weight:700;text-align:right'>{ss.get('median','—')}</td>
          </tr>
          <tr style='border-bottom:1px solid #e0e6ea'>
            <td style='padding:8px 4px;color:#6b8899'>75th percentile</td>
            <td style='padding:8px 4px;font-weight:700;text-align:right'>{ss.get('p75','—')}</td>
          </tr>
          <tr>
            <td style='padding:8px 4px;color:#6b8899'>90th percentile</td>
            <td style='padding:8px 4px;font-weight:700;text-align:right'>{ss.get('p90','—')}</td>
          </tr>
        </table>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # High-risk appointments table
    st.markdown("**Top High-Risk Appointments**")
    hr = pred.get("high_risk_appointments", [])
    if hr:
        hr_df = pd.DataFrame(hr)
        # Rename columns nicely
        col_map = {
            "appointment_id": "ID", "provider": "Provider",
            "patient_type": "Patient", "channel": "Channel",
            "day_of_week": "Day", "lead_time_days": "Lead (days)",
            "appointment_type": "Type", "risk_score": "Risk Score",
            "status": "Actual Status"
        }
        hr_df = hr_df.rename(columns={k: v for k, v in col_map.items() if k in hr_df.columns})
        st.dataframe(hr_df, use_container_width=True, hide_index=True)
    else:
        st.info("No high-risk appointments identified.")


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — PRESCRIPTIVE
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    narrator_box(narrator.narrate_prescriptive(presc, desc, currency=currency_symbol), "#e8923a")
    section_header("03 · Prescriptive", "What to do — prioritised recommendations", "#e8923a")

    recs       = presc.get("recommendations", [])
    agent_acts = presc.get("agent_actions", [])
    quick_wins = presc.get("quick_wins", [])
    summary    = presc.get("summary", {})

    # Summary strip
    s1, s2, s3 = st.columns(3)
    s1.metric("Recommendations",   summary.get("total_recommendations", 0))
    s2.metric("High Priority",     summary.get("high_priority", 0))
    s3.metric("Agent Actions",     summary.get("total_agent_actions", 0))

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # Recommendations
    st.markdown("#### Prioritised Recommendations")
    for r in recs:
        priority   = r.get("priority", 1)
        card_class = "high" if priority <= 2 else ("med" if priority <= 4 else "")
        st.markdown(f"""
        <div class='rx-card {card_class}'>
          <div style='display:flex;align-items:flex-start;gap:16px'>
            <div style='background:#e8f8f5;border-radius:10px;width:38px;height:38px;flex-shrink:0;
                        display:flex;align-items:center;justify-content:center;
                        font-size:15px;font-weight:800;color:#2ea393'>0{priority}</div>
            <div style='flex:1'>
              <div style='font-weight:700;font-size:15px;color:#1a3c4d;margin-bottom:6px'>{r['title']}</div>
              <div style='font-size:13px;color:#6b8899;line-height:1.65;margin-bottom:8px'>{r['rationale']}</div>
              <div style='font-size:13px;color:#1a3c4d;font-weight:500;margin-bottom:10px'>→ {r['action']}</div>
              <div style='display:flex;gap:8px;flex-wrap:wrap'>
                <span class='cw-badge badge-green'>↑ {r['impact']}</span>
                <span class='cw-badge badge-amber'>🤖 {r['agent']}</span>
              </div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)

    # Agent actions
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown("#### What the AI Agents Would Do Right Now")
    a_cols = st.columns(len(agent_acts) if agent_acts else 1)
    for i, a in enumerate(agent_acts):
        with a_cols[i]:
            st.markdown(f"""
            <div class='agent-card'>
              <div style='font-size:11px;font-weight:700;color:#e8923a;text-transform:uppercase;
                          letter-spacing:0.8px;margin-bottom:6px'>{a['agent']}</div>
              <div style='font-size:13px;color:#1a3c4d;line-height:1.5;margin-bottom:8px'>{a['action']}</div>
              <div style='font-size:11px;color:#6b8899;font-weight:500'>⏱ {a['timing']}</div>
            </div>""", unsafe_allow_html=True)

    # Quick wins
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown("#### Quick Wins — Do These Today, No Platform Needed")
    qw_cols = st.columns(len(quick_wins) if quick_wins else 1)
    badge_map = {"High": "badge-green", "Low": "badge-teal", "Medium": "badge-amber"}
    for i, q in enumerate(quick_wins):
        with qw_cols[i]:
            ec = badge_map.get(q["effort"], "badge-teal")
            ic = badge_map.get(q["impact"], "badge-green")
            st.markdown(f"""
            <div class='cw-card'>
              <div style='font-weight:700;font-size:14px;color:#1a3c4d;margin-bottom:8px'>{q['title']}</div>
              <div style='font-size:12px;color:#6b8899;line-height:1.65;margin-bottom:12px'>{q['detail']}</div>
              <span class='cw-badge {ec}'>Effort: {q['effort']}</span>&nbsp;
              <span class='cw-badge {ic}'>Impact: {q['impact']}</span>
            </div>""", unsafe_allow_html=True)


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='margin-top:48px;border-top:1px solid #e0e6ea;padding-top:20px;
            display:flex;justify-content:space-between;align-items:center;
            font-size:12px;color:#6b8899'>
  <span><strong style='color:#1a3c4d'>CadenceWorks</strong> Consulting &nbsp;·&nbsp;
        Descriptive · Predictive · Prescriptive Analytics</span>
  <span>Generated automatically · Confidential</span>
</div>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — ENRICHMENT
# ════════════════════════════════════════════════════════════════════════════
with tab4:
    narrator_box(narrator.narrate_enrichment(holiday_analysis, weather_analysis, upcoming_hols), "#3dbfaa")
    section_header("04 · Enrichment", "Live context layered onto your booking data", "#3dbfaa")

    # ── Status cards ─────────────────────────────────────────────────────────
    ec1, ec2 = st.columns(2)

    holiday_status = "active" if enrich_holidays and holiday_analysis else ("off" if not enrich_holidays else "no_data")
    weather_status = "active" if enrich_weather  and weather_analysis else ("off" if not enrich_weather  else "no_internet")

    def _status_card(col, icon, name, status, note):
        bg    = {"active":"#edf7f3","off":"#f8fafb","no_data":"#fdf5ed","no_internet":"#fdf5ed"}[status]
        bc    = {"active":"#2ea37a","off":"#e0e6ea","no_data":"#e8923a","no_internet":"#e8923a"}[status]
        label = {"active":"Active","off":"Off — toggle on in sidebar","no_data":"On but no data yet","no_internet":"On but no internet connection"}[status]
        lc    = {"active":"#2ea37a","off":"#6b8899","no_data":"#e8923a","no_internet":"#e8923a"}[status]
        col.markdown(f"""<div style='background:{bg};border-left:4px solid {bc};border-radius:0 10px 10px 0;padding:16px 20px'>
            <div style='font-size:20px;margin-bottom:4px'>{icon}</div>
            <div style='font-weight:700;color:#1a3c4d;font-size:14px'>{name}</div>
            <div style='font-size:12px;color:{lc};margin-top:4px'>{label}</div>
            <div style='font-size:11px;color:#6b8899;margin-top:4px'>{note}</div>
        </div>""", unsafe_allow_html=True)

    _status_card(ec1, "🗓", "SA Public Holidays", holiday_status, "Flags holidays, day-before, day-after. No internet needed.")
    _status_card(ec2, "🌦", "Weather — Cape Town", weather_status, "Fetches Open-Meteo historical data. Requires internet.")

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    # ── HOLIDAY SECTION ───────────────────────────────────────────────────────
    if holiday_analysis:
        st.markdown("### 🗓 Public Holiday Impact")

        bands = holiday_analysis.get("noshow_by_proximity", {})
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("<div class='cw-card'>", unsafe_allow_html=True)
            st.markdown("**No-Show Rate by Holiday Proximity**")
            max_v = max((v.get("noshow_rate", 0) for v in bands.values()), default=1)
            order = ["Public Holiday", "Day Before Holiday", "School Holiday Period", "Day After Holiday", "Normal"]
            for band in order:
                if band in bands:
                    v = bands[band]["noshow_rate"]
                    c = "red" if v > 9 else "amber" if v > 7 else "teal"
                    st.markdown(bar_html(band, v, max(max_v, 1), c), unsafe_allow_html=True)
            impact = holiday_analysis.get("holiday_impact_score", 0)
            worst  = holiday_analysis.get("worst_period", "—")
            st.markdown(f"""<div style='background:#fdf5ed;border-left:3px solid #e8923a;
                border-radius:0 8px 8px 0;padding:10px 14px;font-size:12px;color:#7a4f1a;margin-top:12px'>
                <strong>{worst}</strong> has the highest no-show rate —
                <strong>+{impact}%</strong> above normal days.</div>""", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with col2:
            st.markdown("<div class='cw-card'>", unsafe_allow_html=True)
            st.markdown("**Revenue at Risk in Holiday Periods**")
            total_lost = sum(v.get("revenue_lost", 0) for k, v in bands.items() if k != "Normal")
            affected   = holiday_analysis.get("affected_appointments", 0)
            st.metric("Holiday-period revenue lost", fmt_currency(total_lost))
            st.metric("Appointments in holiday periods", f"{affected:,}")
            st.markdown("<br>", unsafe_allow_html=True)
            for band, stats in bands.items():
                if band != "Normal" and stats.get("revenue_lost", 0) > 0:
                    st.markdown(f"""<div style='display:flex;justify-content:space-between;
                        padding:5px 0;border-bottom:1px solid #f0f2f5;font-size:13px'>
                        <span style='color:#6b8899'>{band}</span>
                        <span style='font-weight:700;color:#e05252'>{fmt_currency(stats["revenue_lost"])}</span>
                    </div>""", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # Upcoming holidays
        if upcoming_hols:
            st.markdown("### 📅 Upcoming SA Public Holidays")
            cols = st.columns(min(len(upcoming_hols), 4))
            for i, h in enumerate(upcoming_hols[:4]):
                with cols[i]:
                    urgency = "#e05252" if h["days_until"] <= 7 else "#e8923a" if h["days_until"] <= 21 else "#3dbfaa"
                    cols[i].markdown(f"""<div class='cw-card' style='text-align:center'>
                        <div style='font-size:28px;font-weight:800;color:{urgency}'>{h["days_until"]}</div>
                        <div style='font-size:11px;color:#6b8899;margin-bottom:4px'>days away</div>
                        <div style='font-weight:700;font-size:13px;color:#1a3c4d'>{h["name"]}</div>
                        <div style='font-size:11px;color:#6b8899;margin-top:2px'>{h["date"]}</div>
                    </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""<div class='cw-card' style='text-align:center;padding:32px'>
            <div style='font-size:36px;margin-bottom:12px'>🗓</div>
            <div style='font-weight:700;color:#1a3c4d;margin-bottom:8px'>Holiday data not loaded</div>
            <div style='font-size:13px;color:#6b8899'>Enable <strong>Public Holidays (SA)</strong>
            in the sidebar, then re-upload your file.</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    # ── WEATHER SECTION ───────────────────────────────────────────────────────
    if weather_analysis:
        st.markdown("### 🌦 Weather Impact (Cape Town)")

        rain_bands = weather_analysis.get("noshow_by_rain", {})
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("<div class='cw-card'>", unsafe_allow_html=True)
            st.markdown("**No-Show Rate by Rain Level**")
            max_v = max((v.get("noshow_rate", 0) for v in rain_bands.values()), default=1)
            for band in ["Dry", "Light Rain", "Moderate Rain", "Heavy Rain"]:
                if band in rain_bands:
                    v = rain_bands[band]["noshow_rate"]
                    c = "teal" if band == "Dry" else "amber" if "Light" in band else "red"
                    st.markdown(bar_html(band, v, max(max_v, 1), c), unsafe_allow_html=True)
            uplift = weather_analysis.get("rain_uplift", 0)
            sig    = weather_analysis.get("weather_is_significant", False)
            bg = "#fdf5ed" if sig else "#e8f8f5"
            bc = "#e8923a" if sig else "#3dbfaa"
            tc = "#7a4f1a" if sig else "#2a5f52"
            st.markdown(f"""<div style='background:{bg};border-left:3px solid {bc};
                border-radius:0 8px 8px 0;padding:10px 14px;font-size:12px;color:{tc};margin-top:12px'>
                Rain days show <strong>+{uplift}%</strong> higher no-show rate.
                {"Signal is significant." if sig else "Signal small — monitoring."}</div>""",
                unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with col2:
            st.markdown("<div class='cw-card'>", unsafe_allow_html=True)
            st.markdown("**No-Show Rate by Weather Severity**")
            quartiles = weather_analysis.get("noshow_by_weather_quartile", {})
            max_v = max((v.get("noshow_rate", 0) for v in quartiles.values()), default=1)
            for q, stats in quartiles.items():
                c = "teal" if "Q1" in q else "amber" if "Q2" in q else "red"
                st.markdown(bar_html(q, stats["noshow_rate"], max(max_v, 1), c), unsafe_allow_html=True)
            w_uplift = weather_analysis.get("wind_uplift")
            if w_uplift is not None:
                st.markdown(f"""<div style='background:#fdf5ed;border-left:3px solid #e8923a;
                    border-radius:0 8px 8px 0;padding:10px 14px;font-size:12px;color:#7a4f1a;margin-top:12px'>
                    Windy days (southeaster) add <strong>+{w_uplift}%</strong> no-show risk.</div>""",
                    unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # 7-day forecast
        if weather_forecast:
            st.markdown("### 📡 7-Day Forecast — Reminder Boost Alerts")
            for day in weather_forecast:
                boost = day.get("reminder_boost", False)
                bg  = "#fdf5ed" if boost else "#f8fafb"
                bc  = "#e8923a" if boost else "#e0e6ea"
                icon = "⚠️  Send extra reminder" if boost else "✓  Normal schedule"
                col = "#e8923a" if boost else "#2ea37a"
                st.markdown(f"""<div style='background:{bg};border:1px solid {bc};border-radius:10px;
                    padding:12px 20px;margin-bottom:8px;display:flex;
                    justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px'>
                    <span style='font-weight:700;color:#1a3c4d;min-width:110px'>{day["date"]}</span>
                    <span style='color:#6b8899'>{day["rain_category"]} · {day["precipitation_mm"]:.1f}mm</span>
                    <span style='color:#6b8899'>Risk: {day["weather_risk_score"]:.2f}</span>
                    <span style='font-size:12px;font-weight:700;color:{col}'>{icon}</span>
                </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""<div class='cw-card' style='text-align:center;padding:32px'>
            <div style='font-size:36px;margin-bottom:12px'>🌦</div>
            <div style='font-weight:700;color:#1a3c4d;margin-bottom:8px'>Weather data not loaded</div>
            <div style='font-size:13px;color:#6b8899'>Enable <strong>Weather (Cape Town)</strong>
            in the sidebar. Requires internet — fetches free data from Open-Meteo.</div>
        </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════════════════════
# TAB 5 — SCORE NEW BOOKINGS  (single source of truth: writes to shared DB)
# ════════════════════════════════════════════════════════════════════════════
with tab5:
    narrator_box(narrator.narrate_score_new_bookings(live_sync.get_live_stats()), "#1a3c4d")
    section_header("05 · Score New Bookings",
                   "Add upcoming appointments — instantly scored and shared with Live Monitor & Reminder Agent",
                   "#1a3c4d")

    st.markdown("""
    <div style='background:#1a3c4d;border-radius:14px;padding:20px 28px;margin-bottom:24px'>
      <div style='font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;
                  color:#3dbfaa;margin-bottom:8px'>⚡ One source of truth</div>
      <div style='font-size:13px;color:rgba(255,255,255,0.75);line-height:1.75'>
        Every booking added here — by file or manually — is <strong style='color:white'>risk-scored
        and saved to the shared database</strong>. Live Monitor and Reminder Agent reflect changes
        instantly. No separate uploads required.
      </div>
    </div>""", unsafe_allow_html=True)

    st.markdown("<div style='font-size:10px;color:#3dbfaa;margin-bottom:8px'>v2.1 — upload fix active</div>", unsafe_allow_html=True)
    input_tab_a, input_tab_b = st.tabs(["📁  Upload File", "✏️  Manual Entry"])

    # ── A: File upload ────────────────────────────────────────────────────────
    with input_tab_a:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        if "upload_key" not in st.session_state:
            st.session_state["upload_key"] = 0
        if "last_upload_result" not in st.session_state:
            st.session_state["last_upload_result"] = None

        new_file = st.file_uploader(
            "Upload upcoming bookings (Excel or CSV)",
            type=["xlsx", "xls", "csv"],
            key=f"new_bookings_upload_{st.session_state['upload_key']}",
            help="Same format as your main booking export. All rows are scored and added to the shared database."
        )
        if new_file is not None:
            with st.spinner("Scoring and saving bookings..."):
                n = live_sync.ingest_bytes(new_file.read(), new_file.name)
            st.session_state["last_upload_result"] = (new_file.name, n)
            st.session_state["upload_key"] += 1  # reset uploader widget
            st.rerun()

        # Show result from previous upload (persists after widget reset)
        if st.session_state["last_upload_result"]:
            fname, n = st.session_state["last_upload_result"]
            if n > 0:
                st.success(f"✓ {n} bookings from **{fname}** scored and added.")
            else:
                st.success(f"✓ **{fname}** processed — all bookings already in database.")

    # ── B: Manual entry ───────────────────────────────────────────────────────
    with input_tab_b:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        with st.form("manual_booking_form", clear_on_submit=True):
            mc1, mc2 = st.columns(2)
            m_date = mc1.date_input("Appointment Date", value=datetime.now().date())
            m_time = mc2.time_input("Appointment Time",
                                    value=datetime.strptime("09:00", "%H:%M").time())
            mc3, mc4 = st.columns(2)
            m_name  = mc3.text_input("Patient Name",   placeholder="e.g. Sipho Dlamini")
            m_phone = mc4.text_input("Phone Number",   placeholder="e.g. 0821234567")
            mc5, mc6 = st.columns(2)
            m_type     = mc5.selectbox("Appointment Type",
                                       [
                                        # General Health & Wellness
                                        "GP Consultation", "Extended Consultation", "Tele-Consultation",
                                        "House Call", "After-Hours House Call", "Visa Medical",
                                        "Occupational Medical", "Dietician Consultation",
                                        # Infusion Clinic
                                        "Hydration Drip", "Vitamin Boost Drip", "Immunity Drip",
                                        "Energy & Recovery Drip", "Antioxidant Drip", "Custom IV Infusion",
                                        # Baby Clinic
                                        "Baby Wellness Visit", "Paediatric Consultation", "Immunisation",
                                        # Aesthetics Clinic
                                        "Aesthetics Consultation", "Botox", "Dermal Fillers",
                                        "Chemical Peel", "Threads",
                                        # Woman Wellness
                                        "Women's Health Consult", "Smear Test (PAP)", "Breast Check",
                                        "Contraception Consult", "Pregnancy Consultation", "Fertility Consultation",
                                       ])
            m_provider = mc6.text_input("Provider", value="Dr Marc Davidowitz")
            mc7, mc8 = st.columns(2)
            m_patient_type = mc7.selectbox("Patient Type", ["Existing", "New"])
            m_fee          = mc8.number_input("Fee (R)", min_value=0, value=500, step=50)
            submitted = st.form_submit_button("➕ Add Booking",
                                             use_container_width=True, type="primary")

        if submitted:
            if not m_name:
                st.warning("Please enter a patient name.")
            else:
                appt_dt_str = f"{m_date.strftime('%Y-%m-%d')} {m_time.strftime('%H:%M')}"
                appt_id     = f"MAN-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                n = live_sync.add_manual_booking({
                    "appointment_id":   appt_id,
                    "patient_name":     m_name,
                    "phone":            m_phone,
                    "appt_datetime":    appt_dt_str,
                    "provider":         m_provider,
                    "patient_type":     m_patient_type,
                    "appointment_type": m_type,
                    "fee":              m_fee,
                })
                if n:
                    st.success(
                        f"✓ {m_name} added and scored. Visible in Live Monitor and Reminder Agent.")
                else:
                    st.info("This booking already exists in the database.")
                st.rerun()

    # ── Upcoming bookings table ───────────────────────────────────────────────
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    st.markdown("### 📊 Upcoming Scored Bookings")
    st.markdown("""<div style='font-size:12px;color:#6b8899;margin-bottom:16px'>
        All scored bookings from uploaded files and manual entries.
    </div>""", unsafe_allow_html=True)

    live_df  = live_sync.get_live_bookings(limit=500)
    stats_5  = live_sync.get_live_stats()

    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("Scored Bookings",  len(live_df))
    sc2.metric("🔴 High Risk",     int((live_df["risk_band"] == "High Risk").sum())   if not live_df.empty else 0)
    sc3.metric("🟠 Medium Risk",   int((live_df["risk_band"] == "Medium Risk").sum()) if not live_df.empty else 0)
    sc4.metric("Revenue at Risk",  fmt_currency(float(live_df[live_df["risk_band"] == "High Risk"]["fee"].sum()) if not live_df.empty else 0))

    if live_df.empty:
        st.markdown("""
        <div style='background:#fff;border:1px dashed #e0e6ea;border-radius:12px;
                    padding:32px;text-align:center;font-size:13px;color:#6b8899;margin-top:16px'>
            No bookings yet. Upload a file or add one manually above.
        </div>""", unsafe_allow_html=True)
    else:
        show_cols_5 = [c for c in ["scored_at", "appointment_id", "patient_name",
                                    "appt_datetime", "provider", "appointment_type",
                                    "risk_score", "risk_band", "recommended_action",
                                    "source", "reminded"] if c in live_df.columns]
        show_df_5 = live_df[show_cols_5].rename(columns={
            "scored_at": "Scored", "appointment_id": "ID", "patient_name": "Patient",
            "appt_datetime": "Appt Time", "provider": "Provider",
            "appointment_type": "Type", "risk_score": "Score", "risk_band": "Risk",
            "recommended_action": "Action", "source": "Source", "reminded": "Reminded"
        })
        st.dataframe(show_df_5, use_container_width=True, hide_index=True)

        col_dl5, col_clr5 = st.columns([3, 1])
        col_dl5.download_button(
            "⬇ Download as CSV", show_df_5.to_csv(index=False),
            file_name="cadenceworks_bookings.csv", mime="text/csv",
            use_container_width=True)
        if col_clr5.button("🗑 Clear All", use_container_width=True, key="clr5"):
            live_sync.clear_all()
            st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# TAB 6 — LIVE MONITOR  (reads from shared DB — same data as tab 5)
# ════════════════════════════════════════════════════════════════════════════
with tab6:
    narrator_box(narrator.narrate_live_monitor(live_sync.get_live_stats()), "#e05252")
    section_header("06 · Live Monitor",
                   "Real-time view of all scored bookings — updates the moment a booking is added",
                   "#e05252")

    live_df2 = live_sync.get_live_bookings(limit=500)
    stats_6  = live_sync.get_live_stats()

    # ── Stats strip ───────────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total",              stats_6["total"])
    m2.metric("🔴 High Risk",       stats_6["high_risk"])
    m3.metric("🟠 Medium Risk",     stats_6["medium_risk"])
    m4.metric("Reminders Pending",  stats_6["pending_reminders"])
    m5.metric("Revenue at Risk",    fmt_currency(stats_6["revenue_at_risk"]))

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    if live_df2.empty:
        st.markdown("""
        <div style='background:#fff;border:1px dashed #e0e6ea;border-radius:12px;
                    padding:40px;text-align:center;font-size:13px;color:#6b8899'>
            <div style='font-size:32px;margin-bottom:12px'>📭</div>
            No upcoming bookings yet.<br>
            Go to <strong>⚡ Score New Bookings</strong> and upload a file or add one manually.
        </div>""", unsafe_allow_html=True)
    else:
        # ── Filter bar ────────────────────────────────────────────────────────
        fc1, fc2, fc3 = st.columns(3)
        risk_filter = fc1.selectbox("Risk",
                                    ["All", "High Risk", "Medium Risk", "Low Risk"],
                                    key="lm_risk")
        src_options = ["All"] + sorted(live_df2["source"].dropna().unique().tolist())
        src_filter  = fc2.selectbox("Source", src_options, key="lm_src")
        search_term = fc3.text_input("Search", placeholder="Patient / provider...",
                                     key="lm_search")

        filtered2 = live_df2.copy()
        if risk_filter != "All":
            filtered2 = filtered2[filtered2["risk_band"] == risk_filter]
        if src_filter != "All":
            filtered2 = filtered2[filtered2["source"] == src_filter]
        if search_term:
            mask = (
                filtered2["patient_name"].str.contains(search_term, case=False, na=False) |
                filtered2["provider"].str.contains(search_term, case=False, na=False) |
                filtered2["appointment_id"].str.contains(search_term, case=False, na=False)
            )
            filtered2 = filtered2[mask]

        st.markdown(
            f"<div style='font-size:12px;color:#6b8899;margin-bottom:12px'>"
            f"{len(filtered2)} bookings shown</div>",
            unsafe_allow_html=True)

        # ── High-risk alert cards ─────────────────────────────────────────────
        high_risk2 = filtered2[filtered2["risk_band"] == "High Risk"]
        if not high_risk2.empty:
            st.markdown("#### 🔴 High Risk — Action Required")
            for _, row in high_risk2.iterrows():
                reminded_badge = (
                    "<span style='color:#2ea37a;font-size:11px;font-weight:700'>✓ Reminded</span>"
                    if row.get("reminded")
                    else "<span style='color:#e05252;font-size:11px;font-weight:700'>⚠ Not reminded</span>"
                )
                appt_time = row.get("appt_datetime") or "—"
                st.markdown(f"""
                <div style='background:#fff;border:1px solid #f0cece;
                            border-left:4px solid #e05252;border-radius:0 12px 12px 0;
                            padding:14px 20px;margin-bottom:8px'>
                  <div style='display:flex;justify-content:space-between;
                              align-items:center;flex-wrap:wrap;gap:8px'>
                    <div>
                      <span style='font-weight:700;color:#1a3c4d;font-size:14px'>
                        {row.get("patient_name") or row.get("appointment_id", "—")}
                      </span>
                      <span style='font-size:12px;color:#6b8899;margin-left:10px'>
                        {row.get("appointment_type", "")} · {row.get("provider", "")}
                      </span>
                      <br>
                      <span style='font-size:12px;color:#6b8899'>
                        📅 {appt_time} &nbsp;·&nbsp;
                        📞 {row.get("phone") or "—"} &nbsp;·&nbsp;
                        {row.get("source", "")}
                      </span>
                    </div>
                    <div style='display:flex;align-items:center;gap:12px'>
                      {reminded_badge}
                      <div style='background:#fdf0f0;border:1px solid #e0525233;
                                  border-radius:16px;padding:4px 14px;text-align:center'>
                        <div style='font-size:16px;font-weight:800;color:#e05252'>
                          {row.get("risk_score", 0):.0f}
                        </div>
                        <div style='font-size:9px;color:#e05252;font-weight:700;
                                    text-transform:uppercase'>High Risk</div>
                      </div>
                    </div>
                  </div>
                  <div style='font-size:12px;color:#1a3c4d;margin-top:8px;font-weight:600'>
                    → {row.get("recommended_action", "")}
                  </div>
                </div>""", unsafe_allow_html=True)

        # ── Full table ────────────────────────────────────────────────────────
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown("#### All Bookings")
        show_cols_6 = [c for c in ["scored_at", "appointment_id", "patient_name",
                                    "appt_datetime", "provider", "appointment_type",
                                    "risk_score", "risk_band", "recommended_action",
                                    "phone", "source", "reminded"] if c in filtered2.columns]
        st.dataframe(filtered2[show_cols_6].rename(columns={
            "scored_at": "Scored", "appointment_id": "ID", "patient_name": "Patient",
            "appt_datetime": "Appt Time", "provider": "Provider",
            "appointment_type": "Type", "risk_score": "Score", "risk_band": "Risk",
            "recommended_action": "Action", "phone": "Phone",
            "source": "Source", "reminded": "Reminded"
        }), use_container_width=True, hide_index=True)

    with st.expander("📋 Activity Log"):
        log_df6 = live_sync.get_sync_log(limit=30)
        if log_df6.empty:
            st.info("No activity yet.")
        else:
            st.dataframe(log_df6, use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 7 — REMINDER AGENT  (reads high-risk bookings from shared DB)
# ════════════════════════════════════════════════════════════════════════════
with tab7:
    try:
        _r_stats = reminder_agent.get_reminder_stats()
    except Exception:
        _r_stats = {"queued": 0, "sent": 0, "live_sent": 0}
    try:
        _twilio_ok = reminder_agent.is_twilio_configured(reminder_agent.load_config())
    except Exception:
        _twilio_ok = False
    narrator_box(narrator.narrate_reminder_agent(_r_stats, len(live_sync.get_pending_reminders()), _twilio_ok), "#3dbfaa")
    section_header("07 · Reminder Agent",
                   "Automated WhatsApp reminders — driven by the shared booking database",
                   "#3dbfaa")

    cfg       = reminder_agent.load_config()
    twilio_ok = reminder_agent.is_twilio_configured(cfg)
    r_stats   = reminder_agent.get_reminder_stats()

    # ── Mode banner ───────────────────────────────────────────────────────────
    if twilio_ok:
        st.markdown("""
        <div style='background:#edf7f3;border-left:4px solid #2ea37a;
                    border-radius:0 10px 10px 0;padding:14px 20px;margin-bottom:20px'>
          <span style='font-weight:700;color:#2ea37a'>🟢 Twilio Connected — Live WhatsApp mode</span><br>
          <span style='font-size:12px;color:#2a5f52'>Real messages will be sent to patients.</span>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style='background:#fdf5ed;border-left:4px solid #e8923a;
                    border-radius:0 10px 10px 0;padding:14px 20px;margin-bottom:20px'>
          <div style='font-weight:700;color:#e8923a;margin-bottom:4px'>
            🟡 Dry Run Mode — Twilio not configured
          </div>
          <div style='font-size:12px;color:#7a4f1a'>
            Reminders are simulated and logged. No real messages sent.
            Add Twilio credentials to <code>config.ini</code> to go live.
          </div>
        </div>""", unsafe_allow_html=True)

    # ── Test Message ──────────────────────────────────────────────────────────
    with st.expander("📱 Send a Test WhatsApp Message", expanded=twilio_ok):
        st.markdown("<div style='font-size:13px;color:#6b8899;margin-bottom:12px'>Send a real WhatsApp message to any number to confirm Twilio is working correctly.</div>", unsafe_allow_html=True)
        tc1, tc2 = st.columns([2, 1])
        with tc1:
            test_number = st.text_input(
                "Phone number",
                placeholder="e.g. 0821234567 or +27821234567",
                key="test_wa_number",
                help="Must have joined the Twilio sandbox first by sending the join code to +14155238886"
            )
        with tc2:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            send_test = st.button("Send Test Message", type="primary", disabled=not twilio_ok)

        if not twilio_ok:
            st.caption("⚠️ Add Twilio credentials to config.ini to enable live sending.")

        if send_test:
            if not test_number:
                st.warning("Please enter a phone number.")
            else:
                cfg_test = reminder_agent.load_config()
                practice = cfg_test.get("practice", "name", fallback="CadenceWorks")
                test_msg = (
                    f"👋 Hi! This is a test message from *{practice}* via CadenceWorks.\n\n"
                    f"✅ Your WhatsApp reminders are working correctly.\n\n"
                    f"Patients will receive automated appointment reminders from this number."
                )
                with st.spinner("Sending..."):
                    result = reminder_agent.send_whatsapp(test_number, test_msg, cfg_test)
                if result["success"]:
                    st.success(f"✅ Message sent! Twilio SID: `{result['sid']}`")
                else:
                    st.error(f"❌ Failed: {result['error']}")
                    st.markdown("""
                    **Common fixes:**
                    - Make sure you've joined the sandbox (send the join code to +14155238886 on WhatsApp)
                    - Check your Account SID and Auth Token in config.ini
                    - Make sure the phone number format is correct (e.g. 0821234567)
                    """)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Stats strip ───────────────────────────────────────────────────────────
    ra1, ra2, ra3, ra4 = st.columns(4)
    ra1.metric("Queued",  r_stats["queued"])
    ra2.metric("Sent",    r_stats["sent"])
    ra3.metric("Live",    r_stats["live_sent"])
    ra4.metric("Failed",  r_stats["failed"])

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ── Pull pending bookings from shared DB ──────────────────────────────────
    st.markdown("### 📋 Pending Reminders — from Shared Database")

    pending_df = live_sync.get_pending_reminders()

    if pending_df.empty:
        st.markdown("""
        <div style='background:#fff;border:1px dashed #e0e6ea;border-radius:12px;
                    padding:32px;text-align:center;font-size:13px;color:#6b8899'>
          <div style='font-size:32px;margin-bottom:12px'>✅</div>
          No high-risk bookings pending reminders.<br>
          Add bookings in <strong>⚡ Score New Bookings</strong> — they appear here automatically.
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(
            f"<div style='font-size:13px;color:#6b8899;margin-bottom:16px'>"
            f"<strong style='color:#1a3c4d'>{len(pending_df)}</strong> "
            f"high/medium-risk bookings with appointment times — eligible for reminders.</div>",
            unsafe_allow_html=True)

        # ── Build reminder schedule preview ───────────────────────────────────
        preview_rows = []
        for _, row in pending_df.iterrows():
            appt_dt_str = row.get("appt_datetime", "")
            if not appt_dt_str:
                continue
            try:
                appt_dt = datetime.strptime(str(appt_dt_str), "%Y-%m-%d %H:%M")
            except Exception:
                continue
            band      = row.get("risk_band", "")
            schedules = ["48hr", "2hr"] if band == "High Risk" else ["48hr"]
            for r_type in schedules:
                hours   = 48 if r_type == "48hr" else 2
                send_at = appt_dt - timedelta(hours=hours)
                status  = "🔔 Due now" if send_at <= datetime.now() else "⏳ Scheduled"
                preview_rows.append({
                    "Patient":  row.get("patient_name") or row.get("appointment_id", ""),
                    "Phone":    row.get("phone") or "—",
                    "Appt":     appt_dt.strftime("%d %b %H:%M"),
                    "Reminder": r_type,
                    "Send At":  send_at.strftime("%d %b %H:%M"),
                    "Risk":     band,
                    "Score":    f"{row.get('risk_score', 0):.0f}",
                    "Status":   status,
                    "_id":      row.get("appointment_id", ""),
                })

        if preview_rows:
            # ── Per-patient cards with Send Now button ────────────────────────
            for pr in preview_rows:
                risk_color = "#e05252" if pr["Risk"] == "High Risk" else "#e8923a"
                c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 2])
                c1.markdown(
                    f"<div style='font-weight:700;color:#1a3c4d'>{pr['Patient']}</div>"
                    f"<div style='font-size:11px;color:#6b8899'>{pr['Phone']}</div>",
                    unsafe_allow_html=True)
                c2.markdown(
                    f"<div style='font-size:12px;color:#1a3c4d'>📅 {pr['Appt']}</div>"
                    f"<div style='font-size:11px;color:#6b8899'>{pr['Reminder']} reminder</div>",
                    unsafe_allow_html=True)
                c3.markdown(
                    f"<div style='font-size:12px;color:#6b8899'>Send at</div>"
                    f"<div style='font-size:12px;color:#1a3c4d'>{pr['Send At']}</div>",
                    unsafe_allow_html=True)
                c4.markdown(
                    f"<div style='display:inline-block;background:{risk_color}22;color:{risk_color};"
                    f"border-radius:8px;padding:2px 10px;font-size:11px;font-weight:700'>"
                    f"{pr['Risk']} · {pr['Score']}</div>",
                    unsafe_allow_html=True)
                with c5:
                    btn_label = "📤 Send Now" if twilio_ok else "📋 Dry Run"
                    if st.button(btn_label, key=f"send_now_{pr['_id']}_{pr['Reminder']}",
                                 use_container_width=True):
                        # Find the matching pending row and send immediately
                        match = pending_df[pending_df["appointment_id"] == pr["_id"]]
                        if not match.empty:
                            row = match.iloc[0]
                            try:
                                appt_dt = datetime.strptime(
                                    str(row.get("appt_datetime", "")), "%Y-%m-%d %H:%M")
                            except Exception:
                                appt_dt = datetime.now()
                            appt_dict = {
                                "appointment_id":   row.get("appointment_id", ""),
                                "patient_name":     row.get("patient_name", "Patient"),
                                "provider":         row.get("provider", ""),
                                "appt_datetime":    str(appt_dt),
                                "appointment_type": row.get("appointment_type", "Consultation"),
                                "hours_until":      pr["Reminder"].replace("hr",""),
                            }
                            template_key = f"reminder_{pr['Reminder'].replace('hr','')+'hr'}"
                            # Map display format back to template key
                            if pr["Reminder"] == "48hr":
                                template_key = "reminder_48hr"
                            elif pr["Reminder"] == "2hr":
                                template_key = "reminder_4hr"
                            else:
                                template_key = "reminder_24hr"
                            message = reminder_agent.build_message(template_key, cfg, appt_dict)
                            to_number = row.get("phone", "")
                            if twilio_ok and to_number:
                                result = reminder_agent.send_whatsapp(to_number, message, cfg)
                                if result["success"]:
                                    reminder_agent.log_reminder(
                                        pr["_id"], pr["Reminder"], to_number, message, "sent")
                                    live_sync.mark_reminder_sent(pr["_id"], pr["Reminder"])
                                    st.success(f"✅ Sent to {pr['Patient']}!")
                                else:
                                    st.error(f"❌ Failed: {result['error']}")
                            else:
                                reminder_agent.log_reminder(
                                    pr["_id"], pr["Reminder"], to_number or "(no number)",
                                    message, "dry_run")
                                st.info(f"📋 Dry run — message previewed for {pr['Patient']}")
                                with st.expander("Preview message"):
                                    st.text(message)
                st.markdown("<hr style='border:none;border-top:1px solid #f0f2f5;margin:4px 0'>",
                            unsafe_allow_html=True)

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            col_sched, col_run = st.columns(2)

            with col_sched:
                if st.button("📅 Schedule All Reminders",
                             use_container_width=True, type="primary"):
                    total = 0
                    for _, row in pending_df.iterrows():
                        try:
                            appt_dt = datetime.strptime(
                                str(row.get("appt_datetime", "")), "%Y-%m-%d %H:%M")
                        except Exception:
                            continue
                        appt_dict = {
                            "appointment_id":   row.get("appointment_id", ""),
                            "patient_number":   row.get("phone", ""),
                            "patient_name":     row.get("patient_name", "Patient"),
                            "provider":         row.get("provider", ""),
                            "appt_datetime":    str(appt_dt),
                            "appointment_type": row.get("appointment_type", "Consultation"),
                            "risk_score":       row.get("risk_score", 0),
                            "risk_band":        row.get("risk_band", ""),
                        }
                        n = reminder_agent.schedule_reminders(
                            appt_dict, cfg, dry_run=not twilio_ok)
                        total += n
                    st.success(f"✓ {total} reminders scheduled.")
                    st.rerun()

            with col_run:
                if st.button("▶ Run Agent Now", use_container_width=True):
                    with st.spinner("Running reminder agent..."):
                        actions = reminder_agent.run_once(verbose=False)
                    if actions:
                        for a in actions:
                            icon  = "✅" if a["status"] == "sent" else "📋"
                            label = "SENT" if a["status"] == "sent" else "DRY RUN"
                            st.markdown(f"""
                            <div style='background:#f8fafb;border:1px solid #e0e6ea;
                                        border-radius:10px;padding:14px 18px;margin-bottom:8px'>
                              <div style='display:flex;align-items:center;gap:10px;margin-bottom:8px'>
                                {icon}
                                <strong>{a["appointment_id"]}</strong>
                                <span style='background:#e8f8f5;color:#2ea393;padding:2px 8px;
                                             border-radius:12px;font-size:11px;font-weight:700'>
                                  {a["reminder_type"]}
                                </span>
                                <span style='margin-left:auto;font-size:11px;color:#6b8899'>
                                  [{label}]
                                </span>
                              </div>
                              <div style='background:#f0f2f5;border-radius:8px;padding:10px 14px;
                                          font-size:12px;color:#1a3c4d;white-space:pre-line'>
                                {a["message"]}
                              </div>
                            </div>""", unsafe_allow_html=True)
                            live_sync.mark_reminder_sent(
                                a["appointment_id"], a["reminder_type"])
                    else:
                        st.info("No reminders due right now.")
                    st.rerun()

    # ── Message templates ─────────────────────────────────────────────────────
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    with st.expander("📱 Preview Message Templates"):
        sample_msg = {
            "patient_name":     "Aisha",
            "provider":         "Dr Marc Davidowitz",
            "appt_datetime":    str(datetime.now() + timedelta(days=2)),
            "appointment_type": "GP Consultation",
            "hours_until":      "48",
        }
        for key, label in [
            ("reminder_72hr", "48-Hour Reminder"),
            ("reminder_24hr", "24-Hour Reminder"),
            ("reminder_4hr",  "2-Hour Reminder"),
        ]:
            msg = reminder_agent.build_message(key, cfg, sample_msg)
            st.markdown(f"**{label}**")
            st.markdown(
                f"<div style='background:#e8f8f5;border-radius:10px;padding:14px 18px;"
                f"margin-bottom:12px;font-size:13px;white-space:pre-line;line-height:1.7;"
                f"color:#1a3c4d;border:1px solid #c0e8e0'>{msg}</div>",
                unsafe_allow_html=True)

    with st.expander("📋 Reminder Activity Log"):
        log_df7 = reminder_agent.get_reminder_log(limit=50)
        if log_df7.empty:
            st.info("No activity yet.")
        else:
            st.dataframe(log_df7, use_container_width=True, hide_index=True)

    with st.expander("⚙️ Twilio Setup"):
        st.markdown(f"""
**Status:** {"✓ Connected (LIVE)" if twilio_ok else "✗ Not configured (dry run)"}

To enable live WhatsApp sending, open `config.ini` and fill in:
```
[twilio]
account_sid = ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
auth_token  = your_auth_token_here
from_number = whatsapp:+14155238886
```
Get your credentials at [twilio.com](https://www.twilio.com) — free sandbox available for testing.
        """)


# ════════════════════════════════════════════════════════════════════════════
# TAB 8 — INBOX
# ════════════════════════════════════════════════════════════════════════════
with tab8:
    # ── Init tables ───────────────────────────────────────────────────────────
    inbox_engine.init_inbox_table()
    live_sync.init_db()

    from engine import receptionist as receptionist_engine
    receptionist_engine.init_conversation_table()

    section_header("08 · WhatsApp Conversations",
                   "Every patient conversation — full thread, booking status, live from the database",
                   "#3dbfaa")

    # ── Stats strip ───────────────────────────────────────────────────────────
    try:
        conv_stats = live_sync.get_conversation_stats()
    except Exception:
        conv_stats = {"total": 0, "booked": 0, "no_booking": 0, "in_progress": 0, "conversion_rate": 0}

    cs1, cs2, cs3, cs4, cs5 = st.columns(5)
    cs1.metric("Total Conversations", conv_stats["total"])
    cs2.metric("✅ Booking Made",      conv_stats["booked"])
    cs3.metric("❌ No Booking",        conv_stats["no_booking"])
    cs4.metric("🟡 In Progress",       conv_stats["in_progress"])
    cs5.metric("Conversion Rate",     f"{conv_stats['conversion_rate']}%")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Webhook setup banner ─────────────────────────────────────────────────
    st.markdown("""
    <div style='background:#f8fafb;border-left:4px solid #3dbfaa;
                border-radius:0 10px 10px 0;padding:12px 20px;margin-bottom:20px'>
      <div style='font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;
                  color:#3dbfaa;margin-bottom:6px'>📡 Live WhatsApp Setup</div>
      <div style='font-size:12px;color:#1a3c4d;line-height:1.8'>
        Run in a second terminal:
        <code style='background:#e8f8f5;padding:2px 8px;border-radius:4px'>python3 engine/webhook_server.py</code>
        &nbsp;then expose with:
        <code style='background:#e8f8f5;padding:2px 8px;border-radius:4px'>ngrok http 5005</code>
        &nbsp;and set that URL as your Twilio WhatsApp webhook.
      </div>
    </div>""", unsafe_allow_html=True)

    # ── Conversation history ──────────────────────────────────────────────────
    st.markdown("### 💬 Conversation History")

    try:
        convs_df = live_sync.get_conversations(limit=50)
    except Exception:
        convs_df = pd.DataFrame()

    OUTCOME_CFG = {
        "booking_made": ("#2ea37a", "#edf7f3", "✅ Booking Made"),
        "no_booking":   ("#e05252", "#fdf0f0", "❌ No Booking"),
        "in_progress":  ("#e8923a", "#fdf5ed", "🟡 In Progress"),
    }

    if convs_df.empty:
        st.markdown("""
        <div style='background:#fff;border:1px dashed #e0e6ea;border-radius:12px;
                    padding:40px;text-align:center;font-size:13px;color:#6b8899'>
          <div style='font-size:32px;margin-bottom:12px'>💬</div>
          No conversations yet.<br>
          Use the simulator below to test the booking agent,
          or go live with Twilio and ngrok.
        </div>""", unsafe_allow_html=True)
    else:
        for _, conv in convs_df.iterrows():
            outcome  = conv.get("outcome", "in_progress") or "in_progress"
            col, bg, badge_label = OUTCOME_CFG.get(outcome, OUTCOME_CFG["in_progress"])
            phone    = conv.get("phone", "")
            msg_cnt  = int(conv.get("message_count", 0))
            started  = str(conv.get("started_at", ""))[:16]
            last_msg = str(conv.get("last_message_at", ""))[:16]
            preview  = str(conv.get("last_patient_message", "") or "")[:72]
            booking_id = conv.get("booking_id") or ""
            conv_id  = conv.get("conversation_id", phone)

            # Lookup booking details if booking was made
            booking_detail = ""
            if booking_id:
                try:
                    bdf = live_sync.get_live_bookings(limit=500)
                    bmatch = bdf[bdf["appointment_id"] == booking_id] if not bdf.empty else pd.DataFrame()
                    if not bmatch.empty:
                        b = bmatch.iloc[0]
                        booking_detail = (
                            f"<div style='background:#e8f8f5;border-radius:8px;padding:10px 14px;"
                            f"margin-top:10px;font-size:12px'>"
                            f"<strong style='color:#2ea37a'>Booking created:</strong>&nbsp;"
                            f"{b.get('appointment_type','')} · {b.get('provider','')} · "
                            f"{b.get('appt_datetime','')[:16]} · "
                            f"<strong>#{booking_id}</strong></div>"
                        )
                except Exception:
                    pass

            with st.expander(
                f"{badge_label}  ·  {phone}  ·  {msg_cnt} messages  ·  {last_msg}",
                expanded=(outcome == "in_progress")
            ):
                # Thread view
                try:
                    thread = live_sync.get_conversation_thread(conv_id)
                except Exception:
                    thread = pd.DataFrame()

                if thread.empty:
                    st.markdown("<div style='color:#6b8899;font-size:13px'>No messages.</div>",
                                unsafe_allow_html=True)
                else:
                    thread_html = "<div style='padding:8px 0'>"
                    for _, msg in thread.iterrows():
                        direction = msg.get("direction", "inbound")
                        text = str(msg.get("message", ""))
                        ts   = str(msg.get("ts", ""))[:16]
                        if direction == "inbound":
                            thread_html += (
                                f"<div style='display:flex;justify-content:flex-end;margin-bottom:6px'>"
                                f"<div style='background:#d9fdd3;border-radius:10px 2px 10px 10px;"
                                f"padding:8px 12px;max-width:75%;font-size:12px;color:#111'>"
                                f"{text}"
                                f"<div style='font-size:10px;color:#999;text-align:right;margin-top:3px'>{ts}</div>"
                                f"</div></div>"
                            )
                        else:
                            thread_html += (
                                f"<div style='display:flex;justify-content:flex-start;margin-bottom:6px'>"
                                f"<div style='background:#fff;border:1px solid #e0e6ea;"
                                f"border-radius:2px 10px 10px 10px;"
                                f"padding:8px 12px;max-width:75%;font-size:12px;color:#111'>"
                                f"{text}"
                                f"<div style='font-size:10px;color:#999;margin-top:3px'>{ts} · Virtus Agent</div>"
                                f"</div></div>"
                            )
                    thread_html += "</div>"
                    st.markdown(thread_html, unsafe_allow_html=True)

                if booking_detail:
                    st.markdown(booking_detail, unsafe_allow_html=True)

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    st.markdown("---")

    # ── Simulator (kept at bottom) ────────────────────────────────────────────
    st.markdown("### 🤖 WhatsApp Booking Agent Simulator")
    st.markdown(
        "<div style='font-size:13px;color:#6b8899;margin-bottom:12px'>"
        "Test the full booking flow without needing Twilio. "
        "Messages you send here are logged to the Conversation History above.</div>",
        unsafe_allow_html=True)

    sim_phone = st.text_input(
        "Simulated patient number", value="+27846542499",
        key="sim_phone",
        help="Each number has its own conversation state")

    cfg_sim = reminder_agent.load_config()
    state_now, data_now = receptionist_engine.get_conversation(sim_phone)

    if state_now != "idle":
        st.markdown(
            f"<div style='font-size:11px;color:#3dbfaa;margin-bottom:8px'>"
            f"Current state: <strong>{state_now}</strong></div>",
            unsafe_allow_html=True)

    sim_c1, sim_c2 = st.columns([4, 1])
    with sim_c1:
        sim_msg = st.text_input(
            "Your message",
            placeholder="e.g. Hi, I want to book a house call",
            key="sim_msg")
    with sim_c2:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        send_sim = st.button("Send", type="primary", use_container_width=True)

    if send_sim and sim_msg:
        reply = receptionist_engine.handle_message(sim_phone, sim_msg, cfg_sim)
        st.markdown(
            f"<div style='background:#f0f2f5;border-radius:12px 12px 2px 12px;"
            f"padding:12px 16px;margin:8px 0;max-width:80%;margin-left:auto;"
            f"font-size:13px;color:#1a3c4d'>"
            f"<strong>You:</strong> {sim_msg}</div>"
            f"<div style='background:#edf7f3;border-radius:2px 12px 12px 12px;"
            f"padding:12px 16px;margin:8px 0;max-width:80%;"
            f"font-size:13px;color:#1a3c4d;white-space:pre-line;"
            f"border-left:3px solid #3dbfaa'>"
            f"<strong>Virtus Agent:</strong><br>{reply}</div>",
            unsafe_allow_html=True)
        st.rerun()

    col_rst, col_hint = st.columns([1, 3])
    with col_rst:
        if st.button("Reset conversation", key="reset_convo"):
            receptionist_engine.clear_conversation(sim_phone)
            st.success("Conversation reset.")
            st.rerun()
    with col_hint:
        st.markdown(
            "<div style='font-size:11px;color:#6b8899;padding-top:8px'>"
            "<strong>Demo flow:</strong> Hi, I need a house call "
            "→ YES → 2 → Sarah Smith, 14 Beach Road Sea Point → CONFIRM"
            "</div>",
            unsafe_allow_html=True)


with tab9:
    section_header("09 · 5-Star Revenue Builder",
                   "Automated Google Review requests after every appointment",
                   "#1a3c4d")

    _rev_live  = False
    _rev_stats = {"total_sent": 0, "sent_today": 0, "pending": 0, "recent": []}
    _rev_cfg   = None
    try:
        live_sync.init_db()
        review_agent.init_review_table()
        _rev_cfg   = reminder_agent.load_config()
        _rev_live  = reminder_agent.is_twilio_configured(_rev_cfg)
        _rev_stats = review_agent.get_review_stats()
    except Exception as _e:
        st.warning(f"5-Star Builder initialisation issue: {_e}")

    rc1, rc2, rc3, rc4 = st.columns(4)
    rc1.metric("Total sent",    _rev_stats["total_sent"])
    rc2.metric("Sent today",    _rev_stats["sent_today"])
    rc3.metric("Pending",       _rev_stats["pending"])
    rc4.metric("Twilio",        "Live" if _rev_live else "Sandbox")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown("**Settings**")
    col_a, col_b = st.columns(2)
    with col_a:
        hours_delay = st.slider("Send review request N hours after appointment",
                                min_value=1, max_value=24, value=2)
    with col_b:
        review_link = st.text_input(
            "Google Review link",
            value="https://search.google.com/local/writereview?placeid=ChIJk6pxmzRnzB0RmVJKhf7qzL0"
        )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    with st.expander("Preview review request message"):
        preview = review_agent.build_review_message("Aisha", review_link)
        st.markdown(
            f"<div style='background:#e8f8f5;border-radius:10px;padding:14px 18px;"
            f"font-size:13px;white-space:pre-line;line-height:1.7;"
            f"color:#1a3c4d;border:1px solid #c0e8e0'>{preview}</div>",
            unsafe_allow_html=True
        )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    col_run, col_dry = st.columns(2)
    with col_run:
        if st.button("Send Review Requests Now", use_container_width=True,
                     type="primary", disabled=not _rev_live):
            with st.spinner("Sending..."):
                results = review_agent.run_review_agent(
                    cfg=_rev_cfg, dry_run=False,
                    hours_after=hours_delay, review_link=review_link)
            if results["sent"] > 0:
                st.success(f"{results['sent']} review request(s) sent.")
            elif results["checked"] == 0:
                st.info("No appointments due for a review request right now.")
            if results["errors"] > 0:
                st.warning(f"{results['errors']} message(s) failed.")
            st.rerun()
    with col_dry:
        if st.button("Dry Run (preview only)", use_container_width=True):
            with st.spinner("Running preview..."):
                results = review_agent.run_review_agent(
                    cfg=_rev_cfg, dry_run=True,
                    hours_after=hours_delay, review_link=review_link)
            if results["checked"] == 0:
                st.info("No appointments due right now.")
            else:
                st.success(f"Dry run: would send {results['checked']} message(s).")
                for d in results["details"]:
                    st.markdown(f"<div style='font-size:12px;padding:4px 0;border-bottom:"
                                f"0.5px solid #e0e6ea'>{d['patient_name']} · {d['phone']} · "
                                f"{d['appt_datetime']}</div>", unsafe_allow_html=True)
    if not _rev_live:
        st.warning("Twilio not configured — add credentials to config.ini to go live.")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown("**Recent activity**")
    if _rev_stats["recent"]:
        import pandas as pd
        log_df = pd.DataFrame(_rev_stats["recent"])
        log_df.columns = ["Patient", "Phone", "Sent at", "Status"]
        st.dataframe(log_df, use_container_width=True, hide_index=True)
    else:
        st.markdown("<div style='font-size:13px;color:#6b8899;padding:12px 0'>"
                    "No review requests sent yet.</div>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 10 — PATIENT VOICE ENGINE
# ════════════════════════════════════════════════════════════════════════════
with tab10:
    section_header("10 · Patient Voice Engine",
                   "What your patients are saying — and what it costs you",
                   "#1a3c4d")

    _vc_cfg = None
    _latest = None
    try:
        live_sync.init_db()
        voice_engine.init_voice_tables()
        _vc_cfg = voice_engine.load_config()
    except Exception as _e:
        st.warning(f"Patient Voice Engine initialisation issue: {_e}")
    _google_live    = voice_engine.is_google_configured(_vc_cfg) if _vc_cfg else False
    _anthropic_live = voice_engine.is_anthropic_configured(_vc_cfg) if _vc_cfg else False
    try:
        _latest = voice_engine.get_latest_analysis()
    except Exception:
        _latest = None

    if not _google_live:
        st.warning("Google Places API not configured. Add your API key and Place ID to config.ini.")

    col_refresh, col_force = st.columns([2, 1])
    with col_refresh:
        if st.button("Fetch and Analyse Reviews", use_container_width=True, type="primary"):
            with st.spinner("Fetching reviews from Google and running analysis..."):
                _result, _err = voice_engine.run_voice_engine(_vc_cfg, force_refresh=False)
            if _err:
                st.warning(f"Note: {_err}")
            if _result:
                st.success("Analysis complete.")
                _latest = _result
            st.rerun()
    with col_force:
        if st.button("Force refresh", use_container_width=True):
            with st.spinner("Re-fetching..."):
                _result, _err = voice_engine.run_voice_engine(_vc_cfg, force_refresh=True)
            if _result:
                _latest = _result
            st.rerun()

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    if not _latest:
        st.info("No analysis yet — click Fetch and Analyse Reviews to get started.")
    else:
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Total reviews", _latest["total_reviews"])
        k2.metric("Avg rating",    f"{_latest['avg_rating']} star")
        k3.metric("Positive",      f"{_latest['positive_pct']}%")
        k4.metric("Neutral",       f"{_latest['neutral_pct']}%")
        k5.metric("Negative",      f"{_latest['negative_pct']}%")

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        if _latest.get("summary"):
            st.markdown(f"""
            <div style='background:#1a3c4d;border-radius:14px;padding:20px 28px;margin-bottom:24px'>
              <div style='font-size:11px;font-weight:700;letter-spacing:1.5px;
                          text-transform:uppercase;color:#3dbfaa;margin-bottom:8px'>AI Summary</div>
              <div style='font-size:14px;color:rgba(255,255,255,0.85);line-height:1.8'>
                {_latest['summary']}
              </div>
            </div>""", unsafe_allow_html=True)

        col_themes, col_complaints = st.columns(2)
        with col_themes:
            st.markdown("**Theme breakdown**")
            themes = _latest.get("themes", {})
            if any(v > 0 for v in themes.values()):
                max_v = max(themes.values()) or 1
                for theme, count in sorted(themes.items(), key=lambda x: -x[1]):
                    if count > 0:
                        pct = round(count / max_v * 100)
                        color = "#e05252" if theme in [
                            "booking friction","waiting time","after-hours availability"
                        ] else "#3dbfaa"
                        st.markdown(
                            f"<div style='margin-bottom:10px'>"
                            f"<div style='display:flex;justify-content:space-between;"
                            f"font-size:12px;color:#1a3c4d;margin-bottom:4px'>"
                            f"<span>{theme.title()}</span><span>{count}</span></div>"
                            f"<div style='height:6px;background:#e0e6ea;border-radius:3px'>"
                            f"<div style='width:{pct}%;height:100%;background:{color};"
                            f"border-radius:3px'></div></div></div>",
                            unsafe_allow_html=True
                        )
            else:
                st.markdown("<div style='font-size:13px;color:#6b8899'>No themes detected yet.</div>",
                            unsafe_allow_html=True)

        with col_complaints:
            st.markdown("**Flagged complaints**")
            complaints = _latest.get("complaints", [])
            if complaints:
                for c in complaints:
                    urgency_color = {"high":"#e05252","medium":"#e8923a","low":"#6b8899"}.get(
                        c.get("urgency","low"), "#6b8899")
                    st.markdown(
                        f"<div style='background:#f7f8fb;border-radius:10px;"
                        f"padding:12px 14px;margin-bottom:10px;"
                        f"border-left:3px solid {urgency_color}'>"
                        f"<div style='font-size:11px;color:{urgency_color};"
                        f"font-weight:700;text-transform:uppercase;margin-bottom:4px'>"
                        f"{c.get('urgency','').upper()} — {c.get('category','').title()}</div>"
                        f"<div style='font-size:13px;color:#1a3c4d;margin-bottom:4px'>"
                        f"{c.get('issue','')}</div>"
                        f"<div style='font-size:11px;color:#6b8899'>"
                        f"{c.get('author','')} — {c.get('rating',0)} star</div>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
            else:
                st.markdown("<div style='font-size:13px;color:#6b8899'>No actionable complaints flagged.</div>",
                            unsafe_allow_html=True)

        with st.expander("All reviews"):
            all_revs = voice_engine.get_all_reviews()
            if all_revs:
                for r in all_revs:
                    st.markdown(
                        f"<div style='padding:12px 0;border-bottom:1px solid #e0e6ea'>"
                        f"<div style='font-size:13px;font-weight:600'>{r['author_name']} "
                        f"— {r['rating']} star — {r['review_date']}</div>"
                        f"<div style='font-size:13px;color:#4a5568;line-height:1.6;margin-top:4px'>"
                        f"{r['text'] or 'No text'}</div></div>",
                        unsafe_allow_html=True
                    )
            else:
                st.info("No reviews stored yet.")

        if _latest.get("analysed_at"):
            st.markdown(
                f"<div style='font-size:11px;color:#6b8899;margin-top:16px'>"
                f"Last analysed: {_latest['analysed_at'][:16]}</div>",
                unsafe_allow_html=True
            )


# ════════════════════════════════════════════════════════════════════════════
# TAB 11 — PROOF REPORT
# ════════════════════════════════════════════════════════════════════════════
with tab11:
    section_header("11 · Proof Report",
                   "Monthly before vs after — download as PDF",
                   "#1a3c4d")

    st.markdown("""
    <div style='background:#1a3c4d;border-radius:14px;padding:20px 28px;margin-bottom:24px'>
      <div style='font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;
                  color:#3dbfaa;margin-bottom:8px'>What this report contains</div>
      <div style='font-size:13px;color:rgba(255,255,255,0.75);line-height:1.75'>
        Key metrics this period · Before vs after CadenceWorks · Risk distribution ·
        Top recommendations · 5-Star Builder activity · 60-day guarantee status
      </div>
    </div>""", unsafe_allow_html=True)

    pr_col1, pr_col2 = st.columns(2)
    with pr_col1:
        report_period = st.text_input(
            "Report period",
            value=datetime.now().strftime("%B %Y"),
            help="e.g. March 2026"
        )
    with pr_col2:
        practice_name = st.text_input("Practice name", value="Virtus Health & Medical")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    try:
        _rev_stats_pr = review_agent.get_review_stats()
    except Exception:
        _rev_stats_pr = None

    if st.button("Generate Proof Report PDF",
                 use_container_width=True, type="primary"):
        with st.spinner("Generating PDF..."):
            try:
                pdf_bytes = proof_report.generate(
                    desc=desc,
                    pred=pred,
                    presc=presc,
                    review_stats=_rev_stats_pr,
                    practice_name=practice_name,
                    report_period=report_period,
                )
                st.session_state["proof_report_bytes"] = pdf_bytes
                st.session_state["proof_report_name"]  = (
                    f"CadenceWorks_ProofReport_{report_period.replace(' ','_')}.pdf"
                )
                st.success("PDF ready — click Download below.")
            except Exception as _e:
                st.error(f"Error generating report: {_e}")

    if "proof_report_bytes" in st.session_state:
        st.download_button(
            label="Download Proof Report PDF",
            data=st.session_state["proof_report_bytes"],
            file_name=st.session_state["proof_report_name"],
            mime="application/pdf",
            use_container_width=True,
        )


# ════════════════════════════════════════════════════════════════════════════
# TAB 12 — INSTAGRAM CONTENT AGENT
# ════════════════════════════════════════════════════════════════════════════
with tab12:
    section_header("12 · Instagram Content Agent",
                   "Generate ready-to-publish posts for @virtus_health_ct — powered by AI",
                   "#c9a96e")

    st.markdown("""
    <div style='background:#1a3c4d;border-radius:14px;padding:20px 28px;margin-bottom:24px'>
      <div style='font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;
                  color:#c9a96e;margin-bottom:8px'>⬡ Current Instagram Status</div>
      <div style='display:flex;gap:32px;flex-wrap:wrap'>
        <div><div style='font-size:22px;font-weight:800;color:white'>176</div>
             <div style='font-size:11px;color:rgba(255,255,255,0.45)'>Followers</div></div>
        <div><div style='font-size:22px;font-weight:800;color:white'>7</div>
             <div style='font-size:11px;color:rgba(255,255,255,0.45)'>Posts (abandoned)</div></div>
        <div><div style='font-size:22px;font-weight:800;color:#c9a96e'>3×/week</div>
             <div style='font-size:11px;color:rgba(255,255,255,0.45)'>Target with CadenceWorks</div></div>
        <div><div style='font-size:22px;font-weight:800;color:#3dbfaa'>0 effort</div>
             <div style='font-size:11px;color:rgba(255,255,255,0.45)'>From the practice</div></div>
      </div>
    </div>""", unsafe_allow_html=True)

    # ── Clinic selector ───────────────────────────────────────────────────────
    CLINIC_CONFIG = {
        "Virtus Aesthetics Clinic": {
            "desc": "Botox, dermal fillers, chemical peels, threads, age-reversal — Dr Stefan Bezuidenhout",
            "topics": ["Botox treatments", "dermal fillers", "age-reversal medicine",
                       "chemical peels", "non-surgical cosmetic procedures"],
            "accent": "#c9a96e",
        },
        "Virtus Infusion Clinic": {
            "desc": "IV therapy — hydration, vitamins, antioxidants, immunity, energy drips",
            "topics": ["hydration IV drips", "vitamin boost infusions", "immunity IV therapy",
                       "antioxidant drips", "energy recovery infusions"],
            "accent": "#3dbfaa",
        },
        "General Health & Wellness": {
            "desc": "GP consults, house calls, tele-consults, occupational health",
            "topics": ["premium GP care", "same-day consultations", "after-hours house calls",
                       "tele-consultations", "family medicine"],
            "accent": "#1a3c4d",
        },
        "Virtus Baby Clinic": {
            "desc": "Baby wellness visits, immunisations, paediatric consultations",
            "topics": ["baby wellness", "infant immunisations", "paediatric health",
                       "newborn care", "child health checks"],
            "accent": "#e8923a",
        },
        "Woman Wellness": {
            "desc": "Smear tests, breast checks, contraception, pregnancy, fertility",
            "topics": ["women's health", "PAP smear screening", "contraception advice",
                       "pregnancy care", "fertility consultations"],
            "accent": "#e05252",
        },
    }

    ig_col1, ig_col2 = st.columns([2, 1])
    with ig_col1:
        selected_clinic = st.selectbox(
            "Select clinic",
            list(CLINIC_CONFIG.keys()),
            key="ig_clinic"
        )
    with ig_col2:
        tone = st.selectbox(
            "Tone",
            ["Warm & educational", "Confident & premium", "Friendly & casual"],
            key="ig_tone"
        )

    cfg_data = CLINIC_CONFIG[selected_clinic]
    st.markdown(
        f"<div style='font-size:12px;color:#6b8899;margin-bottom:16px'>"
        f"{cfg_data['desc']}</div>",
        unsafe_allow_html=True)

    anthropic_key_ig = st.text_input(
        "Anthropic API key",
        type="password",
        value=anthropic_api_key if anthropic_api_key else "",
        key="ig_api_key",
        help="Required to generate posts. Add to config.ini as anthropic_api_key."
    )

    gen_col, _ = st.columns([1, 2])
    with gen_col:
        generate_posts = st.button(
            "Generate 3 Posts",
            type="primary",
            use_container_width=True,
            key="ig_gen_btn"
        )

    if generate_posts:
        if not anthropic_key_ig:
            st.warning("Add your Anthropic API key above to generate posts.")
        else:
            topics_str = ", ".join(cfg_data["topics"])
            tone_map = {
                "Warm & educational":  "warm, approachable, and educational — like a brilliant friend who happens to be a doctor",
                "Confident & premium": "confident, premium, and aspirational — Sea Point lifestyle, elevated wellness",
                "Friendly & casual":   "friendly, casual, and relatable — talking to a neighbour in Sea Point",
            }
            tone_desc = tone_map.get(tone, tone_map["Warm & educational"])

            prompt = f"""You are the Instagram content agent for Virtus Health & Medical, a premium private GP practice at The Point Mall in Sea Point, Cape Town. Instagram: @virtus_health_ct. Currently 176 followers and barely posting — you are fixing that.

Generate 3 high-performing Instagram posts for the {selected_clinic} covering: {topics_str}.

Brand voice: {tone_desc}

Practice context:
- 5 doctors: Dr Ryan Jankelowitz (GP, sports, paediatrics), Dr Jane Benjamin (women's health), Dr Stefan Bezuidenhout (aesthetics, IV, anti-ageing), Dr Stacey Fine (women's and children's), Dr Marc Davidowitz (GP)
- Cash-pay practice — affluent, health-conscious Sea Point patients aged 28–60
- 5 clinics: General Health & Wellness, Virtus Infusion Clinic, Virtus Baby Clinic, Virtus Aesthetics Clinic, Woman Wellness
- Hours: Mon–Thu 08:30–17:30, Fri 08:30–16:00, Sat 08:30–12:00
- Book via recomed.co.za or call +27 21 439 1555
- Not contracted to medical aid — patients pay and claim back

Return ONLY valid JSON, no markdown, no backticks:
[
  {{
    "headline": "punchy overlay headline, max 8 words",
    "caption": "3-4 sentence Instagram caption, warm and engaging, ends with a soft CTA, no hashtags",
    "hashtags": "#hashtag1 #hashtag2 — 12-15 hashtags including #virtushealthct #seapoint #capetown #capetowndoctor",
    "visual_direction": "one sentence for the graphic designer describing the image/visual"
  }},
  {{...}},
  {{...}}
]"""

            with st.spinner("Generating posts..."):
                try:
                    import urllib.request, json as _json
                    payload = _json.dumps({
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 1200,
                        "messages": [{"role": "user", "content": prompt}]
                    }).encode()
                    req = urllib.request.Request(
                        "https://api.anthropic.com/v1/messages",
                        data=payload,
                        headers={
                            "Content-Type": "application/json",
                            "x-api-key": anthropic_key_ig,
                            "anthropic-version": "2023-06-01",
                        },
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        result = _json.loads(resp.read())
                    raw_text = result["content"][0]["text"]
                    clean = raw_text.replace("```json", "").replace("```", "").strip()
                    posts = _json.loads(clean)
                    st.session_state["ig_posts"] = posts
                    st.session_state["ig_clinic_name"] = selected_clinic
                    st.session_state["ig_accent"] = cfg_data["accent"]
                    st.rerun()
                except Exception as _e:
                    st.error(f"Generation failed: {_e}")

    # ── Display generated posts ───────────────────────────────────────────────
    if "ig_posts" in st.session_state:
        posts = st.session_state["ig_posts"]
        accent = st.session_state.get("ig_accent", "#3dbfaa")
        clinic_name = st.session_state.get("ig_clinic_name", "")

        st.markdown(
            f"<div style='font-size:11px;font-weight:700;letter-spacing:1.5px;"
            f"text-transform:uppercase;color:{accent};margin:16px 0 12px'>⬡ 3 posts ready — {clinic_name}</div>",
            unsafe_allow_html=True)

        for i, post in enumerate(posts):
            with st.container():
                st.markdown(f"""
                <div style='background:#fff;border:1px solid #e0e6ea;border-radius:14px;
                            border-top:4px solid {accent};padding:20px 24px;margin-bottom:16px'>
                  <div style='font-size:10px;font-weight:700;letter-spacing:1.5px;
                              text-transform:uppercase;color:{accent};margin-bottom:8px'>
                    Post {i+1} of 3
                  </div>
                  <div style='font-size:17px;font-weight:700;color:#1a3c4d;margin-bottom:12px;
                              line-height:1.3'>{post.get("headline","")}</div>
                  <div style='font-size:13px;color:#1a3c4d;line-height:1.7;margin-bottom:12px'>
                    {post.get("caption","")}
                  </div>
                  <div style='font-size:12px;color:#3dbfaa;line-height:1.7;margin-bottom:12px'>
                    {post.get("hashtags","")}
                  </div>
                  <div style='background:#f8fafb;border-radius:8px;padding:10px 14px;
                              font-size:12px;color:#6b8899;border-left:3px solid #e0e6ea'>
                    <strong style='color:#1a3c4d'>Visual:</strong> {post.get("visual_direction","")}
                  </div>
                </div>""", unsafe_allow_html=True)

            c_cap, c_all = st.columns(2)
            full_text = f"{post.get('caption','')}\n\n{post.get('hashtags','')}"
            all_text  = f"HEADLINE:\n{post.get('headline','')}\n\nCAPTION:\n{post.get('caption','')}\n\nHASHTAGS:\n{post.get('hashtags','')}\n\nVISUAL:\n{post.get('visual_direction','')}"
            c_cap.download_button(
                "⬇ Caption + hashtags",
                full_text,
                file_name=f"virtus_post_{i+1}.txt",
                mime="text/plain",
                use_container_width=True,
                key=f"dl_cap_{i}"
            )
            c_all.download_button(
                "⬇ Full brief",
                all_text,
                file_name=f"virtus_post_{i+1}_full.txt",
                mime="text/plain",
                use_container_width=True,
                key=f"dl_all_{i}"
            )

        if st.button("Clear posts", key="ig_clear"):
            del st.session_state["ig_posts"]
            st.rerun()
