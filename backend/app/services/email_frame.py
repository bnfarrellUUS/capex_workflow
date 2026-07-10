"""Brand HTML shell wrapped around every notification email body.

Classic Outlook renders email with Microsoft Word's engine, which cannot draw
rounded corners from CSS and mangles VML on send — but it renders images
perfectly. So the rounded chrome is baked into PNGs (header band with logo +
wordmark, CTA buttons, bottom closing strip) generated at 2x in
backend/app/assets/. The same markup goes to every client: the Outlook sender
attaches each referenced asset under Content-ID ``capexflow-<name>`` and the
in-app preview swaps in data-URIs, so preview and sent email are identical.

Everything else is table-based with inline CSS (Word ignores div layout and
padding on <a>).
"""

NAVY = "#0B2A4A"
SKY = "#93BBF5"
BLUE = "#2563EB"

FONT = "Arial,Helvetica,sans-serif"

CID_PREFIX = "capexflow-"

# asset name -> file in backend/app/assets (the Outlook sender attaches these)
ASSET_FILES = {
    "header": "email_header.png",
    "bottom": "email_bottom.png",
    "btn-assigned": "email_btn_assigned.png",
    "btn-approved": "email_btn_approved.png",
    "btn-rejected": "email_btn_rejected.png",
    "btn-finance-ready": "email_btn_finance_ready.png",
}

# template type -> (asset name, display width, display height, alt label)
BUTTONS = {
    "ASSIGNED": ("btn-assigned", 173, 44, "Review & approve"),
    "APPROVED": ("btn-approved", 162, 44, "View the request"),
    "REJECTED": ("btn-rejected", 167, 44, "Open the request"),
    "FINANCE_READY": ("btn-finance-ready", 252, 44, "Complete the finance section"),
}

BUTTON_LABELS = {type_: b[3] for type_, b in BUTTONS.items()}


def _cid_src(name):
    return f"cid:{CID_PREFIX}{name}"


def _button(button_type, href, asset_src):
    import html as _html
    name, w, h, label = BUTTONS[button_type]
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" '
        'style="margin:20px 0 4px;"><tr><td>'
        f'<a href="{_html.escape(href, quote=True)}">'
        f'<img src="{asset_src(name)}" width="{w}" height="{h}" '
        f'alt="{_html.escape(label)}" style="display:block;border:0;"></a>'
        "</td></tr></table>"
    )


def wrap(body_html, *, redirect_note=None, button_type=None, button_href=None,
         asset_src=_cid_src):
    banner = ""
    if redirect_note:
        banner = (
            '<table role="presentation" width="640" align="center" cellpadding="0" '
            'cellspacing="0" style="margin:0 auto 12px;"><tr>'
            '<td bgcolor="#FEF3C7" style="padding:10px 16px;border-radius:8px;'
            f'font:13px {FONT};color:#92400E;">{redirect_note}</td>'
            "</tr></table>"
        )
    button = ""
    if button_type and button_href:
        button = _button(button_type, button_href, asset_src)
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'bgcolor="#EEF3FB"><tr><td align="center" style="padding:24px;">'
        f"{banner}"
        '<table role="presentation" width="640" cellpadding="0" cellspacing="0">'
        # rounded navy header band (logo + wordmark baked into the image)
        f'<tr><td><img src="{asset_src("header")}" width="640" height="85" '
        'alt="United Uptime Services — CAPEX Flow" '
        'style="display:block;border:0;"></td></tr>'
        # editable body region (+ the locked CTA button, when configured)
        '<tr><td bgcolor="#ffffff" style="padding:24px 28px;'
        f'font:15px/1.5 {FONT};color:#0B1B2B;">'
        f"{body_html}{button}</td></tr>"
        # footer
        '<tr><td bgcolor="#ffffff" style="padding:16px 28px;'
        f'border-top:1px solid #E2E8F0;font:12px {FONT};color:#64748B;">'
        "Automated message from CAPEX Flow — please do not reply.</td></tr>"
        # rounded white closing strip
        f'<tr><td><img src="{asset_src("bottom")}" width="640" height="14" '
        'alt="" style="display:block;border:0;"></td></tr>'
        "</table></td></tr></table>"
    )
