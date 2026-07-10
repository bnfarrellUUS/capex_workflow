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

import html as _html

NAVY = "#0B2A4A"
SKY = "#93BBF5"
BLUE = "#2563EB"

FONT = "Arial,Helvetica,sans-serif"
LOGO_CID = "capexflow-logo"  # Content-ID the Outlook sender attaches the logo under


def _button(label, href):
    """Locked CTA button below the editable body. One markup for every client:
    color + padding live on the <td> (Outlook's Word engine ignores padding on
    <a>), border-radius rounds it everywhere except Outlook desktop, which
    cannot draw rounded corners. (A VML roundrect was tried and abandoned —
    Outlook re-processes HTMLBody through Word on send, which mangles VML and
    truncated the label.) Lives in the frame, never inside Quill-editable HTML."""
    label_esc = _html.escape(label)
    href_esc = _html.escape(href, quote=True)
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" '
        'style="margin:20px 0 4px;"><tr>'
        f'<td bgcolor="{BLUE}" style="border-radius:8px;padding:12px 22px;">'
        f'<a href="{href_esc}" style="font:bold 15px {FONT};color:#ffffff;'
        f'text-decoration:none;">{label_esc}</a>'
        "</td></tr></table>"
    )


def wrap(body_html, *, redirect_note=None, logo_src=f"cid:{LOGO_CID}",
         button_label=None, button_href=None):
    banner = ""
    if redirect_note:
        banner = (
            '<table role="presentation" width="640" align="center" cellpadding="0" '
            'cellspacing="0" style="margin:0 auto 12px;"><tr>'
            '<td bgcolor="#FEF3C7" style="padding:10px 16px;border-radius:8px;'
            f'font:13px {FONT};color:#92400E;">{redirect_note}</td>'
            "</tr></table>"
        )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'bgcolor="#EEF3FB"><tr><td align="center" style="padding:24px;">'
        f"{banner}"
        '<table role="presentation" width="640" cellpadding="0" cellspacing="0" '
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
        # editable body region (+ the locked CTA button, when configured)
        f'<tr><td style="padding:24px 28px;font:15px/1.5 {FONT};color:#0B1B2B;">'
        f"{body_html}"
        f"{_button(button_label, button_href) if button_label and button_href else ''}"
        "</td></tr>"
        # footer
        '<tr><td style="padding:16px 28px;border-top:1px solid #E2E8F0;'
        f'border-radius:0 0 12px 12px;font:12px {FONT};color:#64748B;">'
        "Automated message from CAPEX Flow — please do not reply.</td></tr>"
        "</table></td></tr></table>"
    )
