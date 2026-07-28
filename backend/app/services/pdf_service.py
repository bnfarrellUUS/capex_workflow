"""Build a one-document record of a request: details, approvals, finance.

Split in two on purpose. `request_pdf_sections` decides *what* goes in the
document and returns plain dicts — no reportlab, so the content rules (which
sections appear, how values format) are unit-testable without parsing PDF
bytes. `render_pdf` turns those dicts into a PDF and is the only part that
knows about reportlab.

Sections follow the admin's hidden-wizard-sections config, so a request whose
Economic step is hidden doesn't print a page of blank economic fields.
"""
import os
from decimal import Decimal

from app.serialization import money_str

BRAND_NAVY = "#0B2A4A"
BRAND_SKY = "#93BBF5"

_ASSETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
_HEADER_PNG = os.path.join(_ASSETS_DIR, "email_header.png")

_FLAGS = [
    ("budgeted", "Budgeted"),
    ("replacement", "Replacement"),
    ("health_safety", "Health & safety"),
    ("revenue_generating", "Revenue generating"),
    ("environmental", "Environmental"),
    ("competitive_bids", "Competitive bids"),
    ("lease_recommended", "Lease recommended"),
]

# (attribute, label, formatter key): "money" → $1,234.56, "ratio" → 12.5
# (Numeric(9,4) would otherwise print 12.5000), "plain" → as-is.
_ECONOMIC = [
    ("asset_life", "Asset / project life", "plain"),
    ("irr_after_tax", "IRR after tax (%)", "ratio"),
    ("first_year_ebit", "First-year EBIT", "money"),
    ("annual_savings", "Annual savings", "money"),
    ("payback_years", "Payback (years)", "ratio"),
    ("npv_savings", "NPV of future savings", "money"),
]

_FINANCE_COSTS = [
    ("cost_autos_trucks", "Autos & trucks"),
    ("cost_machinery", "Machinery & equipment"),
    ("cost_improvements", "Building improvements"),
    ("cost_furniture", "Furniture & fixtures"),
    ("cost_it_computer", "IT & computer"),
    ("cost_misc", "Miscellaneous"),
]


def _money(value):
    if value is None:
        return "—"
    return f"${Decimal(value):,.2f}"


def _plain(value):
    if value is None or value == "":
        return "—"
    return str(value)


def _ratio(value):
    """Ratios are Numeric(9,4); print 12.5 rather than 12.5000."""
    if value is None:
        return "—"
    return money_str(value)


def _date(value):
    return value.strftime("%b %d, %Y") if value else "—"


def _datetime(value):
    # Stored naive UTC, same as the detail page's approval history.
    return value.strftime("%b %d, %Y %I:%M %p") if value else "—"


def _useful_life(req):
    if req.useful_life_years is None and req.useful_life_months is None:
        return "—"
    parts = []
    if req.useful_life_years:
        parts.append(f"{req.useful_life_years} yr")
    if req.useful_life_months:
        parts.append(f"{req.useful_life_months} mo")
    return " ".join(parts) or "0"


def _equipment_total(req):
    return sum((Decimal(i.cost) for i in req.equipment_items if i.cost is not None), Decimal(0))


def request_pdf_sections(req, hidden):
    """The document's content as plain dicts, honoring hidden wizard sections."""
    shows = lambda key: key not in hidden  # noqa: E731 - trivial local predicate
    sections = [
        {"kind": "fields", "title": "Summary", "fields": [
            ("Request number", req.number),
            ("Status", req.status),
            ("Requested by", req.requestor.name if req.requestor else "—"),
            ("Division", f"{req.division.number} — {req.division.name}" if req.division else "—"),
            ("Request date", _date(req.request_date)),
            ("Total cost", _money(req.total_cost)),
        ]},
        {"kind": "fields", "title": "Basic info", "fields": (
            [("Asset / project description", _plain(req.description))]
            + [(label, "Yes" if getattr(req, key) else "No") for key, label in _FLAGS]
        )},
    ]

    if shows("description"):
        sections.append({"kind": "text", "title": "Justification",
                         "text": _plain(req.justification)})
    if shows("effect_on_ops"):
        sections.append({"kind": "text", "title": "Effect on operations",
                         "text": _plain(req.effect_on_operations)})

    if shows("asset_details"):
        rows = [["Units", "Condition", "Type", "Make", "Model", "Cost"]]
        for item in req.equipment_items:
            rows.append([str(item.units), item.condition, _plain(item.type),
                         _plain(item.make), _plain(item.model), _money(item.cost)])
        sections.append({
            "kind": "table", "title": "Asset details", "rows": rows,
            "total": f"Asset total: {_money(_equipment_total(req))}",
            "empty_note": "No line items." if len(rows) == 1 else None,
        })

    if shows("economic"):
        formatters = {"money": _money, "ratio": _ratio, "plain": _plain}
        sections.append({"kind": "fields", "title": "Economic analysis", "fields": [
            (label, formatters[fmt](getattr(req, key))) for key, label, fmt in _ECONOMIC
        ]})

    # Nothing to print before Finance fills this in.
    if req.finance_completed:
        fields = [(label, _money(getattr(req, key))) for key, label in _FINANCE_COSTS]
        fields += [
            ("Breakdown total", _money(sum(
                (Decimal(getattr(req, key)) for key, _ in _FINANCE_COSTS
                 if getattr(req, key) is not None), Decimal(0)))),
            ("Asset number", _plain(req.asset_number)),
            ("GL account", _plain(req.gl_account)),
            ("Useful life", _useful_life(req)),
            ("In-service date", _date(req.in_service_date)),
        ]
        sections.append({"kind": "fields", "title": "Finance cost breakdown", "fields": fields})

    actions = sorted(req.actions, key=lambda a: (a.created_at is None, a.created_at))
    rows = []
    if actions:
        rows.append(["Action", "Level", "By", "Date", "Comment"])
        for a in actions:
            rows.append([a.action, str(a.level) if a.level else "—",
                         a.actor.name if a.actor else "—",
                         _datetime(a.created_at), _plain(a.comment)])
    sections.append({
        "kind": "table", "title": "Approval history", "rows": rows,
        "empty_note": "No approval actions yet." if not actions else None,
    })

    sections.append({
        "kind": "list", "title": "Attachments",
        "items": [f"{a.filename} ({a.size / 1024:.1f} KB)" for a in req.attachments],
        "empty_note": "No attachments." if not req.attachments else None,
    })
    return sections


def pdf_filename(req):
    return f"{req.number}.pdf"


def render_pdf(sections, title):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether)
    import io

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter, title=title,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.6 * inch, bottomMargin=0.7 * inch)
    body_width = doc.width

    base = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=base["Heading1"], fontSize=16, spaceAfter=2,
                        textColor=colors.HexColor(BRAND_NAVY))
    h2 = ParagraphStyle("h2", parent=base["Heading2"], fontSize=10.5, spaceBefore=14,
                        spaceAfter=4, textColor=colors.HexColor(BRAND_NAVY))
    body = ParagraphStyle("body", parent=base["BodyText"], fontSize=9, leading=12,
                          alignment=TA_LEFT)
    muted = ParagraphStyle("muted", parent=body, textColor=colors.HexColor("#64748B"))

    story = []
    if os.path.exists(_HEADER_PNG):
        # Reuse the email header band so the PDF matches the notification look.
        story.append(Image(_HEADER_PNG, width=body_width, height=body_width * 85 / 640))
        story.append(Spacer(1, 12))
    story.append(Paragraph(title, h1))

    table_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BRAND_SKY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(BRAND_NAVY)),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])

    for section in sections:
        block = [Paragraph(section["title"], h2)]
        kind = section["kind"]
        if kind == "fields":
            rows = [[Paragraph(f"<b>{label}</b>", body), Paragraph(str(value), body)]
                    for label, value in section["fields"]]
            t = Table(rows, colWidths=[body_width * 0.38, body_width * 0.62])
            t.setStyle(TableStyle([
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -2), 0.3, colors.HexColor("#EEF3FB")),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                ("LEFTPADDING", (0, 0), (0, -1), 0),
            ]))
            block.append(t)
        elif kind == "text":
            block.append(Paragraph(section["text"].replace("\n", "<br/>"), body))
        elif kind == "table":
            if section["rows"]:
                cells = [[Paragraph(f"<b>{c}</b>" if i == 0 else c, body) for c in row]
                         for i, row in enumerate(section["rows"])]
                t = Table(cells, repeatRows=1)
                t.setStyle(table_style)
                block.append(t)
            if section.get("total"):
                block.append(Spacer(1, 4))
                block.append(Paragraph(f"<b>{section['total']}</b>", body))
        elif kind == "list":
            for item in section["items"]:
                block.append(Paragraph(f"• {item}", body))
        if section.get("empty_note"):
            block.append(Paragraph(section["empty_note"], muted))
        story.append(KeepTogether(block) if kind != "table" else block[0])
        if kind == "table":
            story.extend(block[1:])

    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(doc_.leftMargin, 0.45 * inch,
                          "CAPEX Flow — United Uptime Services")
        canvas.drawRightString(doc_.pagesize[0] - doc_.rightMargin, 0.45 * inch,
                               f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def build_request_pdf(req, hidden):
    sections = request_pdf_sections(req, hidden)
    return render_pdf(sections, f"Capital Request {req.number}")
