"""Brand HTML shell wrapped around every notification email body.

Table-based layout with inline CSS: Outlook desktop renders HTML with the Word
engine, which ignores div layouts, max-width, and padding on <a> — structure
must come from tables + bgcolor/padding on <td>. border-radius is kept for
clients that support it (browser preview, Outlook web) and degrades to square
corners in Outlook desktop. Colors from the UUS CAPEX Flow brand.

The header shows the Capital-Cycle logo mark. Outlook can't render SVG or
(reliably) data URIs, so the sender attaches backend/app/assets/email_logo.png
under Content-ID LOGO_CID and the default ``logo_src`` references it as
``cid:...``; the in-app preview passes a data-URI ``logo_src`` instead.
"""

NAVY = "#0B2A4A"
SKY = "#93BBF5"

FONT = "Arial,Helvetica,sans-serif"
LOGO_CID = "capexflow-logo"  # Content-ID the Outlook sender attaches the logo under


def wrap(body_html, *, redirect_note=None, logo_src=f"cid:{LOGO_CID}"):
    banner = ""
    if redirect_note:
        banner = (
            '<table role="presentation" width="600" align="center" cellpadding="0" '
            'cellspacing="0" style="margin:0 auto 12px;"><tr>'
            '<td bgcolor="#FEF3C7" style="padding:10px 16px;border-radius:8px;'
            f'font:13px {FONT};color:#92400E;">{redirect_note}</td>'
            "</tr></table>"
        )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'bgcolor="#EEF3FB"><tr><td align="center" style="padding:24px;">'
        f"{banner}"
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" '
        'bgcolor="#ffffff" style="border:1px solid #E2E8F0;border-radius:12px;">'
        # header band: logo mark + wordmark
        f'<tr><td bgcolor="{NAVY}" style="padding:20px 28px;'
        'border-radius:12px 12px 0 0;">'
        '<table role="presentation" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="padding-right:14px;"><img src="{logo_src}" width="40" '
        'height="40" alt="CAPEX Flow" style="display:block;border:0;"></td>'
        f'<td><div style="font:bold 20px {FONT};color:#ffffff;">'
        "United Uptime Services</div>"
        f'<div style="font:13px {FONT};color:{SKY};letter-spacing:.5px;">'
        "CAPEX Flow</div></td>"
        "</tr></table></td></tr>"
        # editable body region
        f'<tr><td style="padding:24px 28px;font:15px/1.5 {FONT};color:#0B1B2B;">'
        f"{body_html}</td></tr>"
        # footer
        '<tr><td style="padding:16px 28px;border-top:1px solid #E2E8F0;'
        f'border-radius:0 0 12px 12px;font:12px {FONT};color:#64748B;">'
        "Automated message from CAPEX Flow — please do not reply.</td></tr>"
        "</table></td></tr></table>"
    )
