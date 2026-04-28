"""
CadenceWorks — Proof Report Generator
=======================================
Generates a monthly PDF report for Virtus Health showing
before vs after across all key metrics.

The report includes:
  - Executive summary with key numbers
  - No-show rate: baseline vs current
  - Revenue recovered in rand
  - Risk score distribution
  - Google Reviews generated (from 5-Star Builder)
  - Prescriptive recommendations status
  - Month-on-month trend

Usage:
  from engine import proof_report
  pdf_bytes = proof_report.generate(desc, pred, presc, review_stats)
"""

import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

# ── Brand colours ──────────────────────────────────────────────────────────────
NAVY   = colors.HexColor("#1a3c4d")
TEAL   = colors.HexColor("#3dbfaa")
AMBER  = colors.HexColor("#e8923a")
RED    = colors.HexColor("#e05252")
GREEN  = colors.HexColor("#2ea37a")
MUTED  = colors.HexColor("#6b8899")
LIGHT  = colors.HexColor("#f7f8fb")
BORDER = colors.HexColor("#e0e6ea")
WHITE  = colors.white

W, H = A4
MARGIN = 18 * mm


# ── Styles ─────────────────────────────────────────────────────────────────────

def _styles():
    return {
        "title": ParagraphStyle(
            "title", fontName="Helvetica-Bold", fontSize=22,
            textColor=WHITE, leading=28, alignment=TA_LEFT
        ),
        "subtitle": ParagraphStyle(
            "subtitle", fontName="Helvetica", fontSize=11,
            textColor=colors.HexColor("#a8deda"), leading=16, alignment=TA_LEFT
        ),
        "section": ParagraphStyle(
            "section", fontName="Helvetica-Bold", fontSize=10,
            textColor=TEAL, leading=14, spaceAfter=4,
            spaceBefore=16, alignment=TA_LEFT
        ),
        "label": ParagraphStyle(
            "label", fontName="Helvetica", fontSize=9,
            textColor=MUTED, leading=12, alignment=TA_LEFT
        ),
        "body": ParagraphStyle(
            "body", fontName="Helvetica", fontSize=10,
            textColor=NAVY, leading=15, alignment=TA_LEFT
        ),
        "bold": ParagraphStyle(
            "bold", fontName="Helvetica-Bold", fontSize=10,
            textColor=NAVY, leading=15, alignment=TA_LEFT
        ),
        "big_num": ParagraphStyle(
            "big_num", fontName="Helvetica-Bold", fontSize=26,
            textColor=NAVY, leading=30, alignment=TA_CENTER
        ),
        "big_num_green": ParagraphStyle(
            "big_num_green", fontName="Helvetica-Bold", fontSize=26,
            textColor=GREEN, leading=30, alignment=TA_CENTER
        ),
        "big_num_red": ParagraphStyle(
            "big_num_red", fontName="Helvetica-Bold", fontSize=26,
            textColor=RED, leading=30, alignment=TA_CENTER
        ),
        "metric_label": ParagraphStyle(
            "metric_label", fontName="Helvetica", fontSize=8,
            textColor=MUTED, leading=11, alignment=TA_CENTER
        ),
        "summary": ParagraphStyle(
            "summary", fontName="Helvetica", fontSize=10,
            textColor=WHITE, leading=16, alignment=TA_LEFT
        ),
        "footer": ParagraphStyle(
            "footer", fontName="Helvetica", fontSize=8,
            textColor=MUTED, leading=11, alignment=TA_CENTER
        ),
    }


# ── Helper builders ────────────────────────────────────────────────────────────

def _hr(story):
    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=BORDER, spaceAfter=8, spaceBefore=4
    ))


def _metric_card(label, value, value_style="big_num", sub=None):
    """Single metric card — returns a Table for layout."""
    s = _styles()
    val_para = Paragraph(str(value), s[value_style])
    lbl_para = Paragraph(label, s["metric_label"])
    items = [val_para, lbl_para]
    if sub:
        items.append(Paragraph(sub, s["metric_label"]))

    card = Table([[item] for item in items],
                 colWidths=[42 * mm])
    card.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), LIGHT),
        ("ROUNDEDCORNERS", [6]),
        ("TOPPADDING",  (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return card


def _comparison_row(label, baseline, current, currency=True):
    """Before vs after row for the comparison table."""
    s  = _styles()
    prefix = "R" if currency else ""
    fmt = lambda v: f"{prefix}{v:,.0f}" if currency else f"{v:.1f}%"

    diff = current - baseline
    if currency:
        diff_str = f"+R{diff:,.0f}" if diff > 0 else f"-R{abs(diff):,.0f}"
        diff_col = GREEN if diff > 0 else RED
    else:
        diff_str = f"+{diff:.1f}%" if diff > 0 else f"{diff:.1f}%"
        # For no-show rate, lower is better
        diff_col = GREEN if diff < 0 else RED

    return [
        Paragraph(label,           s["body"]),
        Paragraph(fmt(baseline),   s["body"]),
        Paragraph(fmt(current),    s["body"]),
        Paragraph(diff_str, ParagraphStyle(
            "diff", fontName="Helvetica-Bold", fontSize=10,
            textColor=diff_col, leading=15
        )),
    ]


# ── Main generator ─────────────────────────────────────────────────────────────

def generate(
    desc,
    pred,
    presc,
    review_stats=None,
    baseline=None,
    practice_name="Virtus Health & Medical",
    report_period=None,
) -> bytes:
    """
    Generate the Proof Report PDF and return as bytes.

    Args:
        desc:          Output of descriptive.run()
        pred:          Output of predictive.run()
        presc:         Output of prescriptive.run()
        review_stats:  Output of review_agent.get_review_stats() or None
        baseline:      Dict with baseline KPIs from day 1, or None (uses desc KPIs)
        practice_name: Name of the practice
        report_period: String like "March 2026" or None (uses current month)

    Returns:
        PDF as bytes — pass to st.download_button
    """
    buf    = io.BytesIO()
    doc    = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN,  bottomMargin=MARGIN,
    )

    s      = _styles()
    story  = []
    kpis   = desc.get("kpis", {})
    period = report_period or datetime.now().strftime("%B %Y")
    now    = datetime.now().strftime("%d %B %Y")

    # Use current data as baseline if none provided
    if baseline is None:
        baseline = {
            "no_show_rate":      kpis.get("no_show_rate", 0),
            "revenue_lost":      kpis.get("revenue_lost", 0),
            "completion_rate":   kpis.get("completion_rate", 0),
            "total_appointments": kpis.get("total_appointments", 0),
        }

    # ── Cover header ──────────────────────────────────────────────────────────
    header_data = [[
        Paragraph(f"<b>{practice_name}</b>", s["title"]),
        Paragraph(now, ParagraphStyle(
            "date", fontName="Helvetica", fontSize=10,
            textColor=colors.HexColor("#a8deda"), alignment=TA_RIGHT
        )),
    ]]
    header_table = Table(header_data, colWidths=[120 * mm, 51 * mm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), NAVY),
        ("TOPPADDING",   (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 14),
        ("LEFTPADDING",  (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(header_table)

    # Sub-header bar
    sub_data = [[
        Paragraph("CadenceWorks Proof Report", s["subtitle"]),
        Paragraph(period, ParagraphStyle(
            "period", fontName="Helvetica-Bold", fontSize=11,
            textColor=TEAL, alignment=TA_RIGHT, leading=16
        )),
    ]]
    sub_table = Table(sub_data, colWidths=[120 * mm, 51 * mm])
    sub_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), colors.HexColor("#0f2a38")),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("LEFTPADDING",  (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(sub_table)
    story.append(Spacer(1, 12))

    # ── KPI summary cards ─────────────────────────────────────────────────────
    story.append(Paragraph("KEY METRICS THIS PERIOD", s["section"]))
    _hr(story)

    ns_rate     = kpis.get("no_show_rate", 0)
    rev_lost    = kpis.get("revenue_lost", 0)
    comp_rate   = kpis.get("completion_rate", 0)
    total_appts = kpis.get("total_appointments", 0)
    risk_high   = pred.get("risk_distribution", {}).get("High Risk", 0)
    reviews_sent = review_stats.get("total_sent", 0) if review_stats else 0

    ns_style  = "big_num_green" if ns_rate < 8 else "big_num_red"
    rev_style = "big_num_red" if rev_lost > 0 else "big_num_green"

    cards = Table([[
        _metric_card("No-show rate",        f"{ns_rate}%",             ns_style),
        _metric_card("Revenue lost",         f"R{rev_lost:,.0f}",       rev_style),
        _metric_card("Completion rate",      f"{comp_rate}%",           "big_num"),
        _metric_card("Total appointments",   str(total_appts),          "big_num"),
    ]], colWidths=[43 * mm] * 4, hAlign="LEFT")
    cards.setStyle(TableStyle([
        ("LEFTPADDING",  (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(cards)
    story.append(Spacer(1, 14))

    # ── Before vs After comparison ────────────────────────────────────────────
    story.append(Paragraph("BEFORE vs AFTER CADENCEWORKS", s["section"]))
    _hr(story)

    comp_header = [
        Paragraph("Metric",    s["bold"]),
        Paragraph("Baseline",  s["bold"]),
        Paragraph("Current",   s["bold"]),
        Paragraph("Change",    s["bold"]),
    ]
    comp_rows = [comp_header]
    comp_rows.append(_comparison_row(
        "No-show rate",
        baseline.get("no_show_rate", ns_rate),
        ns_rate,
        currency=False,
    ))
    comp_rows.append(_comparison_row(
        "Revenue lost to no-shows",
        baseline.get("revenue_lost", rev_lost),
        rev_lost,
        currency=True,
    ))
    comp_rows.append(_comparison_row(
        "Completion rate",
        baseline.get("completion_rate", comp_rate),
        comp_rate,
        currency=False,
    ))

    comp_table = Table(comp_rows, colWidths=[68 * mm, 32 * mm, 32 * mm, 38 * mm])
    comp_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  WHITE),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0),  9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, LIGHT]),
        ("GRID",          (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(comp_table)
    story.append(Spacer(1, 14))

    # ── Risk distribution ─────────────────────────────────────────────────────
    story.append(Paragraph("RISK DISTRIBUTION — UPCOMING APPOINTMENTS", s["section"]))
    _hr(story)

    risk_dist = pred.get("risk_distribution", {})
    high  = risk_dist.get("High Risk",   0)
    med   = risk_dist.get("Medium Risk", 0)
    low   = risk_dist.get("Low Risk",    0)
    total_risk = high + med + low or 1

    risk_rows = [[
        Paragraph("Risk level", s["bold"]),
        Paragraph("Count",      s["bold"]),
        Paragraph("% of total", s["bold"]),
        Paragraph("Action",     s["bold"]),
    ]]
    for band, count, action, col in [
        ("High Risk",   high, "3-reminder sequence (72hr, 24hr, 4hr)", RED),
        ("Medium Risk", med,  "Single 24hr reminder",                   AMBER),
        ("Low Risk",    low,  "No action required",                      GREEN),
    ]:
        risk_rows.append([
            Paragraph(band,                         ParagraphStyle("rb", fontName="Helvetica-Bold",
                                                    fontSize=10, textColor=col, leading=15)),
            Paragraph(str(count),                   s["body"]),
            Paragraph(f"{round(count/total_risk*100)}%", s["body"]),
            Paragraph(action,                       s["label"]),
        ])

    risk_table = Table(risk_rows, colWidths=[35 * mm, 22 * mm, 28 * mm, 85 * mm])
    risk_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  WHITE),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0),  9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, LIGHT]),
        ("GRID",          (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(risk_table)
    story.append(Spacer(1, 14))

    # ── Top recommendations ───────────────────────────────────────────────────
    recs = presc.get("recommendations", [])[:3]
    if recs:
        story.append(Paragraph("TOP RECOMMENDATIONS", s["section"]))
        _hr(story)

        for i, rec in enumerate(recs, 1):
            rec_data = [[
                Paragraph(f"{i}", ParagraphStyle(
                    "rn", fontName="Helvetica-Bold", fontSize=16,
                    textColor=TEAL, leading=20, alignment=TA_CENTER
                )),
                [
                    Paragraph(rec.get("title", ""), s["bold"]),
                    Spacer(1, 3),
                    Paragraph(rec.get("rationale", rec.get("description", "")), s["label"]),
                ],
            ]]
            rec_table = Table(rec_data, colWidths=[16 * mm, 155 * mm])
            rec_table.setStyle(TableStyle([
                ("BACKGROUND",   (0, 0), (-1, -1), LIGHT),
                ("TOPPADDING",   (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 10),
                ("LEFTPADDING",  (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW",    (0, 0), (-1, -1), 0.5, BORDER),
            ]))
            story.append(KeepTogether(rec_table))
            story.append(Spacer(1, 4))

        story.append(Spacer(1, 10))

    # ── 5-Star builder summary ────────────────────────────────────────────────
    if review_stats and review_stats.get("total_sent", 0) > 0:
        story.append(Paragraph("5-STAR REVENUE BUILDER", s["section"]))
        _hr(story)

        rev_cards = Table([[
            _metric_card("Review requests sent", str(review_stats["total_sent"]), "big_num"),
            _metric_card("Sent this month",      str(review_stats.get("sent_today", 0)), "big_num"),
        ]], colWidths=[85 * mm, 85 * mm], hAlign="LEFT")
        rev_cards.setStyle(TableStyle([
            ("LEFTPADDING",  (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING",   (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ]))
        story.append(rev_cards)
        story.append(Spacer(1, 14))

    # ── Guarantee callout ─────────────────────────────────────────────────────
    guarantee_data = [[
        Paragraph(
            "<b>60-Day Zero Risk Guarantee</b><br/><br/>"
            "If CadenceWorks has not recovered more than your monthly retainer "
            "in measurable revenue within the first 60 days, your next month is "
            "completely free. The numbers above are your proof.",
            s["summary"]
        )
    ]]
    guarantee_table = Table(guarantee_data, colWidths=[171 * mm])
    guarantee_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), NAVY),
        ("TOPPADDING",   (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 14),
        ("LEFTPADDING",  (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
    ]))
    story.append(guarantee_table)
    story.append(Spacer(1, 10))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Paragraph(
        f"CadenceWorks · Confidential · Generated {now} · cadenceworkscalculator.streamlit.app",
        s["footer"]
    ))

    doc.build(story)
    buf.seek(0)
    return buf.read()
