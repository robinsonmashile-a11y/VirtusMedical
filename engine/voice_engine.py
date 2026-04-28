"""
CadenceWorks — Patient Voice Engine
Pulls Google Reviews via Places API and analyses them with Claude.
"""
import sqlite3
import json
import re
import urllib.request
import urllib.error
import urllib.parse
import configparser
from datetime import datetime, timedelta
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.ini"
DB_PATH     = Path(__file__).parent.parent / "virtus_health.db"

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
GOOGLE_PLACES_URL = "https://maps.googleapis.com/maps/api/place/details/json"
CACHE_HOURS = 6

COMPLAINT_CATEGORIES = [
    "booking friction", "waiting time", "after-hours availability",
    "staff communication", "pricing or billing", "doctor bedside manner",
    "facility or cleanliness", "follow-up or continuity of care",
]


def init_voice_tables():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS google_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id TEXT UNIQUE, author_name TEXT, rating INTEGER,
            text TEXT, time INTEGER, review_date TEXT, fetched_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS voice_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysed_at TEXT, total_reviews INTEGER, avg_rating REAL,
            positive_pct INTEGER, neutral_pct INTEGER, negative_pct INTEGER,
            themes TEXT, complaints TEXT, summary TEXT, raw_response TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_reviews(reviews):
    conn = sqlite3.connect(DB_PATH)
    for r in reviews:
        conn.execute("""
            INSERT OR REPLACE INTO google_reviews
            (review_id, author_name, rating, text, time, review_date, fetched_at)
            VALUES (?,?,?,?,?,?,?)
        """, (r.get("review_id",""), r.get("author_name",""), r.get("rating",0),
              r.get("text",""), r.get("time",0), r.get("review_date",""), str(datetime.now())))
    conn.commit()
    conn.close()


def get_cached_reviews(max_age_hours=CACHE_HOURS):
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    conn   = sqlite3.connect(DB_PATH)
    rows   = conn.execute("""
        SELECT review_id, author_name, rating, text, review_date, fetched_at
        FROM google_reviews WHERE fetched_at >= ? ORDER BY time DESC
    """, (cutoff.strftime("%Y-%m-%d %H:%M:%S"),)).fetchall()
    conn.close()
    return [{"review_id": r[0], "author_name": r[1], "rating": r[2],
             "text": r[3], "review_date": r[4], "fetched_at": r[5]} for r in rows]


def get_all_reviews():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT review_id, author_name, rating, text, review_date, fetched_at
        FROM google_reviews ORDER BY time DESC
    """).fetchall()
    conn.close()
    return [{"review_id": r[0], "author_name": r[1], "rating": r[2],
             "text": r[3], "review_date": r[4], "fetched_at": r[5]} for r in rows]


def save_analysis(result):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO voice_analysis
        (analysed_at, total_reviews, avg_rating, positive_pct, neutral_pct,
         negative_pct, themes, complaints, summary, raw_response)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (str(datetime.now()), result.get("total_reviews",0), result.get("avg_rating",0),
          result.get("positive_pct",0), result.get("neutral_pct",0), result.get("negative_pct",0),
          json.dumps(result.get("themes",{})), json.dumps(result.get("complaints",[])),
          result.get("summary",""), result.get("raw_response","")))
    conn.commit()
    conn.close()


def get_latest_analysis():
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute("""
        SELECT analysed_at, total_reviews, avg_rating, positive_pct, neutral_pct,
               negative_pct, themes, complaints, summary
        FROM voice_analysis ORDER BY analysed_at DESC LIMIT 1
    """).fetchone()
    conn.close()
    if not row:
        return None
    return {"analysed_at": row[0], "total_reviews": row[1], "avg_rating": row[2],
            "positive_pct": row[3], "neutral_pct": row[4], "negative_pct": row[5],
            "themes": json.loads(row[6] or "{}"), "complaints": json.loads(row[7] or "[]"),
            "summary": row[8]}


def load_config():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH)
    return cfg


def is_google_configured(cfg):
    api_key  = cfg.get("google", "api_key",  fallback="")
    place_id = cfg.get("google", "place_id", fallback="")
    return api_key not in ("", "YOUR_GOOGLE_CLOUD_API_KEY") and \
           place_id not in ("", "YOUR_GOOGLE_PLACE_ID")


def is_anthropic_configured(cfg):
    return cfg.get("anthropic", "api_key", fallback="") not in ("", "YOUR_API_KEY_HERE")


def fetch_google_reviews(cfg):
    api_key  = cfg.get("google", "api_key",  fallback="")
    place_id = cfg.get("google", "place_id", fallback="")
    params = urllib.parse.urlencode({
        "place_id": place_id, "fields": "name,rating,reviews,user_ratings_total",
        "key": api_key, "reviews_sort": "newest",
    })
    try:
        req = urllib.request.Request(f"{GOOGLE_PLACES_URL}?{params}",
                                     headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        if data.get("status") != "OK":
            return [], f"Google API error: {data.get('status')} — {data.get('error_message','')}"
        reviews = data.get("result", {}).get("reviews", [])
        parsed = []
        for r in reviews:
            parsed.append({
                "review_id":   f"{r.get('author_name','')}_{r.get('time',0)}",
                "author_name": r.get("author_name", "Anonymous"),
                "rating":      r.get("rating", 0),
                "text":        r.get("text", ""),
                "time":        r.get("time", 0),
                "review_date": datetime.fromtimestamp(r.get("time",0)).strftime("%d %b %Y")
                               if r.get("time") else "",
            })
        return parsed, None
    except Exception as ex:
        return [], str(ex)


def _fallback_analysis(reviews, avg_rating, error_msg):
    total    = len(reviews)
    positive = sum(1 for r in reviews if r["rating"] >= 4)
    negative = sum(1 for r in reviews if r["rating"] <= 2)
    neutral  = total - positive - negative
    return {
        "total_reviews": total, "avg_rating": round(avg_rating, 1),
        "positive_pct": round(positive/total*100) if total else 0,
        "neutral_pct":  round(neutral/total*100)  if total else 0,
        "negative_pct": round(negative/total*100) if total else 0,
        "themes": {c: 0 for c in COMPLAINT_CATEGORIES}, "complaints": [],
        "summary": f"Basic analysis only — Claude unavailable ({error_msg}). "
                   f"{positive} positive, {neutral} neutral, {negative} negative reviews.",
        "raw_response": error_msg,
    }


def analyse_reviews_with_claude(reviews, cfg):
    api_key = cfg.get("anthropic", "api_key", fallback="")
    if not reviews:
        return {"total_reviews": 0, "avg_rating": 0, "positive_pct": 0,
                "neutral_pct": 0, "negative_pct": 0, "themes": {}, "complaints": [],
                "summary": "No reviews available yet.", "raw_response": ""}

    avg_rating   = sum(r["rating"] for r in reviews) / len(reviews)
    reviews_text = "\n\n".join([
        f"Review {i+1} — {r['rating']} stars ({r['review_date']})\n{r['text'] or '[Rating only]'}"
        for i, r in enumerate(reviews)
    ])

    prompt = f"""You are analysing Google Reviews for Virtus Health & Medical — a premium GP practice in Sea Point, Cape Town.

{len(reviews)} reviews:

{reviews_text}

Respond ONLY with valid JSON, no preamble:

{{
  "positive_pct": <0-100>,
  "neutral_pct": <0-100>,
  "negative_pct": <0-100>,
  "themes": {{
    "booking friction": <count>,
    "waiting time": <count>,
    "after-hours availability": <count>,
    "staff communication": <count>,
    "pricing or billing": <count>,
    "doctor bedside manner": <count>,
    "facility or cleanliness": <count>,
    "follow-up or continuity of care": <count>
  }},
  "complaints": [
    {{"review_index": <1-based>, "author": "<name>", "rating": <stars>,
      "issue": "<one sentence>", "category": "<theme>", "urgency": "<high|medium|low>"}}
  ],
  "summary": "<2-3 sentences for a practice manager>"
}}

Rules: positive=4-5 stars, neutral=3 stars, negative=1-2 stars. Percentages must sum to 100."""

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001", "max_tokens": 1500,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        ANTHROPIC_API_URL, data=payload,
        headers={"Content-Type": "application/json", "x-api-key": api_key,
                 "anthropic-version": "2023-06-01"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result   = json.loads(resp.read())
            raw_text = result["content"][0]["text"].strip()

            # Extract JSON robustly
            json_text = raw_text
            if "```" in json_text:
                json_text = re.sub(r"```[a-z]*", "", json_text).replace("```", "")
            start = json_text.find("{")
            end   = json_text.rfind("}") + 1
            if start != -1 and end > start:
                json_text = json_text[start:end]

            parsed = json.loads(json_text)
            return {
                "total_reviews": len(reviews), "avg_rating": round(avg_rating, 1),
                "positive_pct": parsed.get("positive_pct", 0),
                "neutral_pct":  parsed.get("neutral_pct",  0),
                "negative_pct": parsed.get("negative_pct", 0),
                "themes":       parsed.get("themes",       {}),
                "complaints":   parsed.get("complaints",   []),
                "summary":      parsed.get("summary",      ""),
                "raw_response": raw_text,
            }
    except urllib.error.HTTPError as e:
        return _fallback_analysis(reviews, avg_rating, f"Anthropic API error {e.code}: {e.read().decode()}")
    except json.JSONDecodeError as e:
        return _fallback_analysis(reviews, avg_rating, f"JSON parse error: {e}")
    except Exception as ex:
        return _fallback_analysis(reviews, avg_rating, str(ex))


def run_voice_engine(cfg=None, force_refresh=False):
    init_voice_tables()
    if cfg is None:
        cfg = load_config()

    if not force_refresh:
        cached = get_cached_reviews(CACHE_HOURS)
        if cached:
            analysis = analyse_reviews_with_claude(cached, cfg)
            save_analysis(analysis)
            return analysis, None

    if not is_google_configured(cfg):
        all_reviews = get_all_reviews()
        if all_reviews:
            analysis = analyse_reviews_with_claude(all_reviews, cfg)
            save_analysis(analysis)
            return analysis, "Google API not configured — using stored reviews"
        return None, "Google API not configured and no stored reviews found"

    reviews, error = fetch_google_reviews(cfg)
    if error:
        stored = get_all_reviews()
        if stored:
            analysis = analyse_reviews_with_claude(stored, cfg)
            save_analysis(analysis)
            return analysis, f"Google fetch failed — using stored reviews"
        return None, error

    if reviews:
        save_reviews(reviews)
    else:
        reviews = get_all_reviews()
        if not reviews:
            return {
                "total_reviews": 0, "avg_rating": 0.0,
                "positive_pct": 0, "neutral_pct": 0, "negative_pct": 0,
                "themes": {c: 0 for c in COMPLAINT_CATEGORIES}, "complaints": [],
                "summary": "No reviews found yet. The 5-Star Builder will start generating reviews automatically.",
            }, None

    analysis = analyse_reviews_with_claude(reviews, cfg)
    save_analysis(analysis)
    return analysis, None
