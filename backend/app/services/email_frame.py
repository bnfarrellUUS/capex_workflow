"""Brand HTML shell wrapped around every notification email body.
Inline CSS only (email-client requirement); colors from the UUS CAPEX Flow brand.
"""

NAVY = "#0B2A4A"
SKY = "#93BBF5"


def wrap(body_html, *, redirect_note=None):
    banner = ""
    if redirect_note:
        banner = (
            '<div style="max-width:600px;margin:0 auto 12px;background:#FEF3C7;'
            'color:#92400E;padding:10px 16px;border-radius:8px;'
            'font:13px/1.4 Arial,Helvetica,sans-serif;">'
            f"{redirect_note}</div>"
        )
    return (
        '<div style="margin:0;padding:24px;background:#EEF3FB;">'
        f"{banner}"
        '<div style="max-width:600px;margin:0 auto;background:#ffffff;'
        "border:1px solid #E2E8F0;border-radius:12px;overflow:hidden;"
        'font-family:Arial,Helvetica,sans-serif;color:#0B1B2B;">'
        f'<div style="background:{NAVY};padding:24px 28px;">'
        '<div style="color:#ffffff;font-size:20px;font-weight:bold;">'
        "United Uptime Services</div>"
        f'<div style="color:{SKY};font-size:13px;letter-spacing:.5px;">CAPEX Flow</div>'
        "</div>"
        '<div style="padding:24px 28px;font-size:15px;line-height:1.5;">'
        f"{body_html}</div>"
        '<div style="padding:16px 28px;border-top:1px solid #E2E8F0;'
        'color:#64748B;font-size:12px;">'
        "Automated message from CAPEX Flow — please do not reply.</div>"
        "</div></div>"
    )
