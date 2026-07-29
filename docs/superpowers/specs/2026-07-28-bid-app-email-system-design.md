# Email system design — Bid Flow

**Date:** 2026-07-28
**Status:** Design, ready to implement
**Source:** extracted from the CAPEX Flow email subsystem (this repo), adapted
for the customer-bid app.

This is a build spec, not a survey. Where CAPEX Flow's code copies over
unchanged it is quoted verbatim and marked **copy**; where the bid domain
forces a change it is marked **change** with the reason. Section 10 of
`BID-APP-STARTER-GUIDE.md` is the two-page summary of this material — this
document supersedes it and goes to implementation depth.

Read `email-rounded-corners-guide.md` (repo root) alongside this. It holds the
Pillow generator for the brand PNGs and the Content-ID attachment recipe, and
should be copied into the bid repo too.

---

## 1. What the system does

Every workflow transition sends a branded HTML email. Admins can edit the
subject, the body (WYSIWYG), and an on/off flag per email type, with `{token}`
placeholders substituted at send time. A runtime delivery mode decides whether
mail goes to the real recipients or is redirected to one test address. Every
send is logged whether or not delivery is enabled.

Four properties are non-negotiable, and everything below exists to protect one
of them:

1. **The sent email looks right in classic Outlook.** Word's rendering engine,
   not a browser. This is why the chrome is images.
2. **The preview equals the sent email**, byte for byte apart from the image
   `src` scheme. An admin who previews has actually seen what ships.
3. **An admin can never break the layout.** They edit a body region; the frame
   is locked.
4. **A customer never receives a test message.** Test mode redirects
   everything, and customer sends are never automatic.

---

## 2. Architecture — five modules, one direction

```
blueprints/bids.py          ← the only place that decides "an email happens now"
        │
        ▼
services/notify.py          ← recipient resolution, delivery mode, NotificationLog
        │
        ├──▶ services/email_template_service.py   ← tokens, defaults, render, preview
        │            │
        │            └──▶ services/email_frame.py ← the locked brand HTML shell
        │
        └──▶ services/email_outlook.py            ← the transport (swappable)
```

Rules that make this hold:

- **Notifications fire from blueprints, never from services.** A service that
  sends mail cannot be called from a test or a batch job without spraying
  email. CAPEX Flow enforces this — `workflow_service` mutates state, the route
  then calls `notify`.
- **`notify.py` is the only caller of the transport.** Replacing Outlook COM
  with SMTP or Microsoft Graph when the app moves to a server is then a
  one-file change. `email_outlook.py` carries that promise in its docstring;
  keep the docstring.
- **`email_frame.py` imports nothing from the app.** It is pure string
  building, which is what makes the preview/sent parity test cheap.
- **Delivery failures are logged, never raised.** A dead Outlook profile must
  not 500 an approval.

---

## 3. Data model

Three tables. **copy** all three; the only change is the FK column name.

### `email_templates`

One row per type, **created only when an admin first customizes it**. Shipped
defaults live in code. This means a fresh database has zero rows and the app
still sends correct mail — and a later change to a shipped default reaches
every install that never customized that type.

```python
class EmailTemplate(db.Model):
    __tablename__ = "email_templates"

    type: Mapped[str] = mapped_column(String(20), primary_key=True)
    subject: Mapped[str] = mapped_column(Text)
    body_html: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    default_subject: Mapped[str] = mapped_column(Text)
    default_body_html: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now())
```

**Three-tier defaults** — the part worth understanding before you simplify it
away:

| Tier | Where | Reset target |
| --- | --- | --- |
| Shipped default | `DEFAULTS` dict in code | what "Reset" gives you before any admin baseline exists |
| Admin default | `default_subject` / `default_body_html` on the row | what "Reset" gives you after **Save as Default** |
| Live | `subject` / `body_html` | what actually sends |

So an admin writes their house wording, clicks **Save as Default**, then
experiments freely and can always get back to *their* baseline rather than the
factory one. Seeding a row copies the shipped default into both tiers.

### `app_settings`

```python
class AppSetting(db.Model):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
```

A generic key/value table, not an email table. Email uses two keys
(`email_mode`, `email_test_recipient`); the bid app will find other uses.

### `notification_logs` — **change**

CAPEX Flow's row is `(request_id, recipient, type, sent_at)`. Two changes for
bids:

```python
class NotificationLog(db.Model):
    __tablename__ = "notification_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    bid_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("bids.id", ondelete="SET NULL"), nullable=True)
    recipient: Mapped[str] = mapped_column(String(255))
    recipient_kind: Mapped[str] = mapped_column(String(10))   # INTERNAL | CUSTOMER
    type: Mapped[str] = mapped_column(String(30))
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
```

`recipient_kind` exists because a customer send has no `User` behind it — the
address comes off a `CustomerContact`. Without the column you cannot answer
"what did we actually mail this customer, and when" without joining against a
user table the address was never in. It also makes the audit query that
matters — *every external message this app has ever sent* — a one-column
filter.

**Log the intended recipient, not the redirected one.** In Test mode the mail
goes to the test address but the log records who it was *for*. CAPEX Flow does
this and it is the only reason a test run's log is readable afterward.

---

## 4. The render pipeline

One path, four steps, used identically by `render()` (sending) and `preview()`
(the admin editor):

```
context_for(bid, **extra)   → dict of token values, all pre-formatted strings
_substitute(text, ctx)      → replace {token}; HTML-escape values in the body
_polish(body_html)          → give Quill's bare tags inline styles
email_frame.wrap(body, …)   → locked brand shell + CTA button
```

### 4.1 Context building — **change** (bid fields)

Every value arrives as a **display-ready string**. No `Decimal`, no `date`, no
`None` reaching the template. `"—"` is the empty marker.

```python
def context_for(bid, **extra):
    base = (current_app.config.get("APP_BASE_URL") or "").rstrip("/")
    ctx = {
        "number": bid.number,
        "customer": bid.customer.name if bid.customer else "—",
        "owner": bid.owner.name if bid.owner else "—",
        "total": f"${bid.total:,.2f}" if bid.total is not None else "—",
        "valid_until": bid.valid_until.strftime("%B %d, %Y") if bid.valid_until else "—",
        "link": f"{base}/bids/{bid.id}",
    }
    ctx.update(extra)
    return ctx
```

`APP_BASE_URL` must be set in production or every deep link points at
`localhost`. Pair the deep link with a long remember-me cookie (CAPEX Flow uses
30 days) so a link clicked days later doesn't dead-end at a login screen.

### 4.2 Substitution — escape the body, not the subject

```python
def _substitute(text, context, escape=False):
    for key, value in context.items():
        replacement = html.escape(str(value)) if escape else str(value)
        text = text.replace("{" + key + "}", replacement)
    return text
```

Called with `escape=True` for the body and `escape=False` for the subject
(subjects are plain text; escaping there would show `&amp;` in the inbox).
This matters more in a bid app than in CAPEX: customer names, line-item
descriptions, and rejection comments are free text that lands inside HTML.
A customer called `Smith & Sons <Holdings>` must not break the markup.

**Unknown tokens are left intact.** A typo'd `{custmer}` ships as literal
`{custmer}` — visibly wrong to whoever proofreads, rather than silently blank.
Pin this with a test.

### 4.3 Polish — **copy**

Quill emits bare `<p>` and `<blockquote>`. Email clients need inline styles,
and the result must match what the editor showed:

```python
def _polish(body_html):
    return (body_html
            .replace("<p>", '<p style="margin:0;">')
            .replace("<blockquote>",
                     '<blockquote style="margin:12px 0;padding:4px 0 4px 16px;'
                     'border-left:4px solid #CBD5E1;color:#475569;">'))
```

Paragraphs are `margin:0` deliberately — spacing comes from the blank
`<p><br></p>` lines the admin types, so the editor and the email agree on
vertical rhythm.

---

## 5. The locked frame

### 5.1 Why it is images

Classic Outlook renders with **Microsoft Word's engine**. It ignores
`border-radius`, ignores `div` layout and padding on `<a>`, and mangles VML on
send — but it renders images perfectly. So the rounded chrome is baked into
PNGs generated at 2x and displayed at 1x: the header band with logo and
wordmark, each CTA button, and the bottom closing strip. Everything else is
table-based with inline CSS and `bgcolor` on `<td>`.

`email-rounded-corners-guide.md` §4 has the Pillow generator. Run it once and
commit the PNGs; they are build artifacts only in principle.

### 5.2 Asset registry — **change** (bid buttons and audience)

```python
NAVY, SKY, BLUE = "#0B2A4A", "#93BBF5", "#2563EB"
FONT = "Arial,Helvetica,sans-serif"
CID_PREFIX = "bidflow-"

ASSET_FILES = {
    "header":        "email_header.png",
    "bottom":        "email_bottom.png",
    "btn-approve":   "email_btn_approve.png",
    "btn-view":      "email_btn_view.png",
}

# template type -> (asset name, display width, display height, alt label)
# CUSTOMER_BID has no entry: customers have no app account, so there is
# nothing for a CTA to link to. wrap() renders no button when the type is
# absent, which is the same path as a missing href.
BUTTONS = {
    "APPROVAL_NEEDED": ("btn-approve", 173, 44, "Review & approve"),
    "BID_APPROVED":    ("btn-view",    150, 44, "View the bid"),
    "BID_REJECTED":    ("btn-view",    150, 44, "View the bid"),
    "BID_SENT":        ("btn-view",    150, 44, "View the bid"),
}
BUTTON_LABELS = {t: b[3] for t, b in BUTTONS.items()}
```

Two buttons cover four types because a generic label is reusable — CAPEX
Flow's fifth email type shipped with **no new artwork** by reusing the
"View the request" button. Check the existing set before drawing a new one.

`BUTTON_LABELS` is returned by the template API and drawn as the locked,
non-editable button in the admin editor. It must tolerate a missing key: the
editor shows no button preview for `CUSTOMER_BID`.

The display width the generator prints goes in the `<img width=…>` attribute,
not the pixel width. `test_every_button_asset_exists_with_recorded_size` (§9)
guards the two from drifting apart.

### 5.3 `wrap()` — **change** (audience-aware footer)

This is decision **#1**. CAPEX Flow has one audience, so its frame hardcodes
*"Automated message from CAPEX Flow — please do not reply."* A customer
receiving a quote must be able to reply to their salesperson, so that footer is
wrong on exactly the email that matters most.

Add an `audience` parameter, defaulting to internal:

```python
FOOTERS = {
    "INTERNAL": "Automated message from Bid Flow — please do not reply.",
    "CUSTOMER": ("Questions about this quote? Just reply to this email and "
                 "{owner} will get back to you."),
}


def wrap(body_html, *, redirect_note=None, button_type=None, button_href=None,
         audience="INTERNAL", owner="", asset_src=_cid_src):
    ...
    footer = html.escape(FOOTERS[audience].replace("{owner}", owner))
```

`owner` is a plain string, substituted with a local `str.replace` rather than
the template service's `_substitute`. That keeps `email_frame` importing
nothing from the app — the property §2 relies on, and what makes the parity
test a pure-function call.

The rest of `wrap()` copies verbatim. Its shape, for reference:

```python
return (
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
    'bgcolor="#EEF3FB"><tr><td align="center" style="padding:24px;">'
    f"{banner}"                                    # test-mode redirect notice
    '<table role="presentation" width="640" cellpadding="0" cellspacing="0">'
    f'<tr><td><img src="{asset_src("header")}" width="640" height="85" …></td></tr>'
    '<tr><td bgcolor="#ffffff" style="padding:24px 28px;'
    f'font:15px/1.5 {FONT};color:#0B1B2B;">'
    f"{body_html}{button}</td></tr>"               # editable region + locked CTA
    '<tr><td bgcolor="#ffffff" style="padding:16px 28px;'
    f'border-top:1px solid #E2E8F0;font:12px {FONT};color:#64748B;">'
    f"{footer}</td></tr>"
    f'<tr><td><img src="{asset_src("bottom")}" width="640" height="14" …></td></tr>'
    "</table></td></tr></table>"
)
```

Note `asset_src` is injected, not hardcoded. That single parameter is what
makes preview parity possible: the sender passes the `cid:` resolver, the
browser preview passes a base64 data-URI resolver, and **nothing else differs**.

### 5.4 Content-ID delivery

The HTML references `cid:bidflow-header`; the sender scans the HTML for those
references and attaches the matching PNGs with a matching Content-ID. Never
hotlink images from a web server — Outlook blocks remote images by default and
the email arrives as a stack of red X's.

```python
_CID_RE = re.compile(rf"cid:{email_frame.CID_PREFIX}([a-z0-9-]+)")
_PR_ATTACH_CONTENT_ID = "http://schemas.microsoft.com/mapi/proptag/0x3712001F"


def _attach_inline_assets(mail, html):
    for name in sorted(set(_CID_RE.findall(html))):
        filename = email_frame.ASSET_FILES.get(name)
        if not filename:
            continue
        att = mail.Attachments.Add(os.path.join(_ASSETS_DIR, filename))
        att.PropertyAccessor.SetProperty(
            _PR_ATTACH_CONTENT_ID, f"{email_frame.CID_PREFIX}{name}")
```

Scanning the HTML rather than attaching all assets unconditionally means an
email carries only the images it uses.

---

## 6. Template catalog — **change** (bid domain)

### 6.1 Types

| Type | Name (admin UI) | Audience | To | Fires when |
| --- | --- | --- | --- | --- |
| `APPROVAL_NEEDED` | Approval needed | INTERNAL | every approver in the current level's pool | submit, resubmit, advance a level |
| `BID_APPROVED` | Bid approved | INTERNAL | bid owner | final approval |
| `BID_REJECTED` | Bid rejected | INTERNAL | bid owner | rejection |
| `BID_SENT` | Sent to customer | INTERNAL | bid owner (confirmation copy) | after a customer send succeeds |
| `CUSTOMER_BID` | Customer quote | **CUSTOMER** | the customer contact | the explicit Send action only |

Declare that table in code, so nothing has to infer an audience from a type
name:

```python
AUDIENCE = {
    "APPROVAL_NEEDED": "INTERNAL",
    "BID_APPROVED":    "INTERNAL",
    "BID_REJECTED":    "INTERNAL",
    "BID_SENT":        "INTERNAL",
    "CUSTOMER_BID":    "CUSTOMER",
}
```

`render()` reads it and passes it to `wrap()`; the admin editor reads it to
label the customer template distinctly in the tab bar.

`APPROVAL_NEEDED` fans out to **every** approver in the pool, not just the
nominal assignee, because any one of them may act. CAPEX Flow accepted the
same fan-out for its finance notification; expect several near-identical
messages to pile up in the test inbox during Test mode, and don't treat that
as a bug.

A bid priced within policy needs no approval at all — it goes straight to
approved, which means `APPROVAL_NEEDED` never fires but `BID_APPROVED` still
should. Wire the notification to the *state transition*, not to the approval
action.

### 6.2 Tokens

Keep the set small and mostly shared. Per-type extras are declared, not
implicit, so the editor's placeholder panel is accurate.

```python
_COMMON = [
    {"token": "{number}",      "description": "Bid number (e.g. BID000123)"},
    {"token": "{customer}",    "description": "Customer name"},
    {"token": "{owner}",       "description": "Name of the bid owner"},
    {"token": "{total}",       "description": "Bid total, e.g. $182,400.00"},
    {"token": "{valid_until}", "description": "Quote expiry, e.g. August 30, 2026"},
    {"token": "{link}",        "description": "Deep link to the bid in the app"},
]
TOKENS = {
    "APPROVAL_NEEDED": _COMMON + [{"token": "{level}",   "description": "Level awaiting you, e.g. Level 2 of 3"},
                                  {"token": "{reason}",  "description": "Why approval is required, e.g. margin below floor"}],
    "BID_APPROVED":    _COMMON,
    "BID_REJECTED":    _COMMON + [{"token": "{comment}", "description": "Reviewer's rejection comment"}],
    "BID_SENT":        _COMMON + [{"token": "{contact}", "description": "Who it was sent to"}],
    # No {link} — customers have no app account. See below.
    "CUSTOMER_BID":    [t for t in _COMMON if t["token"] != "{link}"]
                       + [{"token": "{contact}", "description": "Customer contact's first name"}],
}
```

`{reason}` is bid-specific and earns its place: approval can be triggered by
total value, a margin floor, a discount ceiling, or non-standard terms, and an
approver opening a cold email needs to know which. Build it in the workflow
service where the rule is evaluated and pass it through as an `extra`.

**`{link}` is absent from `CUSTOMER_BID`'s token list** — customers have no
app account, so there is nowhere for a deep link to go. That template also has
no CTA button (§5.2); the attached PDF is the deliverable. If a public
quote-view URL is ever built, adding the token and a button is the moment to
revisit it.

### 6.3 Shipped defaults

The editable body must stay **round-trippable through Quill**: paragraphs,
bold, and blockquote only. No tables, no `bgcolor`, no VML. Quill strips them,
and in CAPEX Flow that once turned a saved button into invisible
white-on-white text. Anything structural belongs in the locked frame.

```python
_FACTS = (
    "<p><br></p>"
    "<p>Customer: <strong>{customer}</strong></p>"
    "<p>Bid total: <strong>{total}</strong></p>"
    "<p>Valid until: {valid_until}</p>"
)

DEFAULTS = {
    "APPROVAL_NEEDED": {
        "subject": "Action needed: {number} awaiting your {level} approval",
        "body_html": (
            "<p>Bid <strong>{number}</strong> for <strong>{customer}</strong> "
            "needs your <strong>{level}</strong> approval.</p>"
            "<p><br></p><p>Reason approval is required: {reason}</p>" + _FACTS
        ),
    },
    "BID_APPROVED": {
        "subject": "{number} was approved",
        "body_html": (
            "<p>Your bid <strong>{number}</strong> ({total}) for "
            "<strong>{customer}</strong> was <strong>approved</strong>.</p>"
            "<p><br></p><p>It is ready to send to the customer — open the bid "
            "and use <strong>Send to customer</strong>.</p>"
        ),
    },
    "BID_REJECTED": {
        "subject": "{number} was rejected",
        "body_html": (
            "<p>Your bid <strong>{number}</strong> ({total}) was "
            "<strong>rejected</strong>.</p><p><br></p>"
            "<blockquote>Reviewer's comment: {comment}</blockquote><p><br></p>"
            "<p>You can revise and resubmit it.</p>"
        ),
    },
    "BID_SENT": {
        "subject": "{number} was sent to {customer}",
        "body_html": (
            "<p>Bid <strong>{number}</strong> ({total}) was emailed to "
            "<strong>{contact}</strong> with the quote PDF attached.</p>" + _FACTS
        ),
    },
    "CUSTOMER_BID": {
        "subject": "Your quote from United Uptime Services — {number}",
        "body_html": (
            "<p>Hello {contact},</p><p><br></p>"
            "<p>Thank you for the opportunity to quote. Our proposal "
            "<strong>{number}</strong> is attached as a PDF.</p><p><br></p>"
            "<p>Quote total: <strong>{total}</strong><br>"
            "Valid until: <strong>{valid_until}</strong></p><p><br></p>"
            "<p>{owner}</p>"
        ),
    },
}
```

The customer default deliberately carries no internal vocabulary — no
"approval", no "workflow", no margin. Whoever edits it in Admin can still
type something inappropriate; §11 covers why the PDF, not the email, is where
the internal/external separation is actually enforced.

---

## 7. Delivery: recipients, modes, transport

### 7.1 Mode resolution — **copy**

```python
def _delivery(intended):
    settings = settings_service.get_email_settings()
    if settings["mode"] == "test":
        to = settings["test_recipient"] or intended
        note = f"Intended recipient: {intended} (redirected while testing)"
        return to, note
    return intended, None
```

The note becomes an amber banner above the frame. Defaults are **Test mode**
plus `EMAIL_REDIRECT_TO` from config, so a fresh install cannot mail anyone
real before an admin has made a decision.

Test mode redirects **everything, customers included** — decision **#3**. No
exception, no "external addresses pass through". The cost of a wrong redirect
is an internal person seeing a duplicate; the cost of an exception is a
customer receiving a fake quote.

Two independent switches, and both must be on to send:

| Switch | Where | Question it answers |
| --- | --- | --- |
| `EMAIL_ENABLED` | config / env | Does this deployment send mail at all? |
| mode = live | `AppSetting`, admin-toggled | Do messages go to real recipients? |

`EMAIL_ENABLED` defaults to off in the base config, on in dev, and off in
testing. Keep that; the test suite must never touch Outlook.

### 7.2 The emit path — **copy**

```python
def _emit(intended, subject, html, enabled, bid_id, type_,
          recipient_kind="INTERNAL", attachments=None):
    """Always record a NotificationLog; deliver via Outlook when enabled."""
    try:
        log.info("EMAIL to=%s subject=%s", intended, subject)
        db.session.add(NotificationLog(bid_id=bid_id, recipient=intended,
                                       recipient_kind=recipient_kind, type=type_))
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception("notification log failed for %s", intended)
    if not enabled or not current_app.config.get("EMAIL_ENABLED"):
        return
    redirect_to = _delivery(intended)[0]
    try:
        from app.services import email_outlook
        email_outlook.send(redirect_to, subject, "", html=html,
                           attachments=attachments)
    except Exception:
        log.exception("email delivery failed (intended %s)", intended)
```

Three deliberate properties: the log is written **before and regardless of**
delivery; a failed log rolls back but does not stop the send; a failed send is
swallowed. An approval must not 500 because Outlook is closed.

`enabled` is the per-template flag — a disabled template still logs. That is
how you answer "why didn't Jane get her email" without guessing.

### 7.3 Transport — **copy**, with a Reply-To addition

Outlook COM attaches from a **path**, not bytes, so each attachment is written
to a temp file and cleaned up after `Send()`.

```python
def send(to, subject, body, html=None, attachments=None, reply_to=None):
    import pythoncom, win32com.client, shutil, tempfile

    tmpdir = tempfile.mkdtemp(prefix="bidflow-mail-") if attachments else None
    pythoncom.CoInitialize()
    try:
        mail = win32com.client.Dispatch("Outlook.Application").CreateItem(0)
        mail.To, mail.Subject = to, subject
        if reply_to:
            mail.ReplyRecipients.Add(reply_to)
        if html is not None:
            _attach_inline_assets(mail, html)   # cid: brand PNGs
            mail.HTMLBody = html
        else:
            mail.Body = body
        for filename, data in attachments or []:
            path = os.path.join(tmpdir, filename)
            with open(path, "wb") as fh:
                fh.write(data)
            mail.Attachments.Add(path)
        mail.Send()
    finally:
        pythoncom.CoUninitialize()
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
```

`reply_to` is new, and pairs with decision #1: a `CUSTOMER` email sets it to
the bid owner's address so the customer's reply reaches a person, not the
service mailbox. `pywin32` is imported lazily so CI on non-Windows never needs
it.

**Any test that spies on `send` must accept both new keyword arguments.** In
CAPEX Flow, adding `attachments=` broke every existing spy at once; write the
spies with `**kwargs` from the start.

---

## 8. Sending to the customer — decision #2

The app sends, but **never automatically**. Approval sends internal mail only.

- A **Send to customer** button appears on an APPROVED bid, for the owner and
  for managers/admin.
- Clicking it opens a confirmation that names the recipient address and the
  attachment: *"Send bid BID000123 (PDF) to jane.doe@acme.com?"* — the address
  in full, not "the contact".
- The current delivery mode is shown **next to that button**, not only on the
  Admin page. Someone about to mail a customer should not have to remember
  what mode the app is in.
- Only on confirm: send `CUSTOMER_BID`, set `status = SENT`, stamp `sent_at`,
  log an `ApprovalAction` of `SENT_TO_CUSTOMER`, send `BID_SENT` to the owner,
  and write two `NotificationLog` rows (one CUSTOMER, one INTERNAL).
- Re-sending is allowed and logged; each send appends to the trail.

```
POST /api/bids/<id>/send
```

Guards, all returning `ServiceError(msg, 400)`:

- status is `APPROVED`, or `SENT` for a deliberate re-send
- the bid has a customer contact with a non-empty email
- the quote PDF builds

The route builds the PDF, calls `notify.notify_customer_bid(bid, contact)`,
then `notify.notify_bid_sent(bid, contact)`. Notifications fire from the
blueprint, as always.

```python
def notify_customer_bid(bid, contact):
    from app.services import pdf_service
    pdf = pdf_service.build_customer_pdf(bid)
    _send_template(contact.email, "CUSTOMER_BID", bid,
                   audience="CUSTOMER",
                   reply_to=bid.owner.email if bid.owner else None,
                   attachments=[(pdf_service.pdf_filename(bid), pdf)],
                   contact=contact.first_name)
```

---

## 9. API surface and admin UI

### 9.1 Endpoints — **copy**, all `ADMIN`-only

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/email-templates` | list summaries (type, name, subject, enabled, is_custom) |
| GET | `/api/email-templates/<type>` | full template + `tokens` + `button_label` |
| PUT | `/api/email-templates/<type>` | save subject/body/enabled |
| POST | `/api/email-templates/<type>/save-as-default` | promote live → admin default |
| POST | `/api/email-templates/<type>/reset` | admin default → live |
| POST | `/api/email-templates/<type>/preview` | render unsaved draft with sample data |
| GET/PUT | `/api/email-templates/settings` | delivery mode + test recipient |

**Every endpoint returning a template must return the identical shape.** The
client caches these responses interchangeably; in CAPEX Flow a missing
`tokens` field on the PUT response crashed the editor immediately after Save.
Enforce it with one helper and one test:

```python
def _template_out(data):
    data["tokens"] = ets.TOKENS[data["type"]]
    return jsonify(data)
```

### 9.2 Settings schema — decision #4

Do **not** copy CAPEX Flow's `EmailSettingsIn`. Its `field_validator` *raises*
`ValueError`, which trips a known bug: the app-wide `ValidationError` handler
calls `err.errors()`, embedding the raw exception in `ctx`, which `jsonify`
cannot serialize — so a malformed address returns **500 instead of 400**.

Two fixes, apply both in the new app:

```python
# 1. Express the constraint as a type, so no validator raises.
from pydantic import BaseModel, EmailStr
from typing import Literal


class EmailSettingsIn(BaseModel):
    mode: Literal["test", "live"]
    test_recipient: EmailStr
```

```python
# 2. Fix the handler itself, in app/__init__.py
@app.errorhandler(ValidationError)
def _validation(err):
    return jsonify({"error": "Invalid request.",
                    "details": err.errors(include_context=False)}), 400
```

### 9.3 Editor UI — **copy**

`EmailTemplateEditor.tsx` is worth porting close to verbatim. Four things it
gets right:

- **A visual replica of the email frame surrounds the Quill editor** — navy
  header with logo above, locked CTA button and footer below, all
  non-editable, with the caption *"Added automatically."* The admin edits
  inside the same rectangle the recipient will see.
- **A placeholder side panel** lists each token with its description;
  clicking inserts at the cursor via a callback captured through
  `onReady={(insert) => (insertRef.current = insert)}`.
- **Preview opens the server-rendered HTML in a `sandbox=""` iframe.**
  Server-rendered, so it is the real thing; sandboxed, because it is HTML the
  editor can inject anything into.
- **A tab bar switches templates in place**, and switching with unsaved edits
  prompts a discard confirm. Track `dirty` on every field change.

One React gotcha to carry over: mutation responses are **merged** into the
cache, not substituted —

```ts
qc.setQueryData(['email-templates', type], (prev) =>
  prev ? { ...prev, ...updated } : updated)
```

so a response missing a field can never blank out what the page renders from.

The delivery-mode control (`EmailDeliveryMode.tsx`) appears on both the list
page and the editor, and — new for bids — on the bid detail page beside the
Send button. Switching to Live requires a `window.confirm` naming the
consequence, and Live renders as a red pill.

---

## 10. Testing contract

Roughly thirty tests in CAPEX Flow. These are the ones that carry their
weight; write them first, they are cheap because the frame is a pure function.

**Frame**

- body appears inside the wrapper, brand strings present
- markup is table-based — assert `<table` present and no `border-radius` on
  layout containers
- the CTA is an `<img>` inside an `<a href>`
- redirect note renders the amber banner; absent when not passed
- `asset_src` override replaces every `cid:` reference — the parity mechanism
- **every button asset exists on disk and its recorded display size matches
  the file's actual pixel size ÷ 2**, iterating `BUTTONS`
- **`audience="CUSTOMER"` renders the replyable footer, `INTERNAL` the
  do-not-reply one** — new, guards decision #1

**Template service**

- `get()` returns the shipped default when no row exists
- save → reset reverts to the shipped default
- save → save-as-default → save → reset reverts to the *admin* default
- unknown type raises `ServiceError(404)`
- `render()` substitutes tokens and wraps in the frame
- **`render()` HTML-escapes token values in the body** — the `Smith & Sons`
  case
- unknown tokens survive rendering intact
- **preview HTML equals sent HTML** for the same subject/body, comparing after
  normalizing `cid:`/`data:` — the single most valuable test here
- **every shipped default body is Quill-safe**: iterate `DEFAULTS` and assert
  no `<table`, no `bgcolor`, no `v:` VML tag

**Notify**

- a send writes a `NotificationLog` even when `EMAIL_ENABLED` is off
- a disabled template logs but does not send
- Test mode delivers to the test recipient and includes the banner; Live
  delivers to the real recipient with no banner
- the log records the **intended** recipient in both modes
- a raising transport never propagates
- `APPROVAL_NEEDED` reaches every approver in the current level's pool
- **a customer send sets `recipient_kind="CUSTOMER"` and a `reply_to`** — new

Spy on the transport with `**kwargs`, not a fixed signature.

**What tests cannot check:** whether it *looks* right in Outlook. Before
shipping any email change, send yourself a real sample and look at it in
classic Outlook. Browser preview parity is necessary, not sufficient.

---

## 11. Boundary: what the email must not leak

The customer-facing PDF is a **separate builder** from the internal record
copy — different function, different content rules, not a flag on one
function. Cost, margin, and the approval trail exist only in the internal
build. Keep them in separate modules so a change to the internal copy cannot
reach the customer one by accident.

The email body is the weaker boundary: it is admin-editable free text, and
nothing stops someone typing a margin into `CUSTOMER_BID`. Mitigate by
construction rather than validation — **do not expose internal tokens to that
template.** `{margin}`, `{cost}`, and `{discount}` are absent from
`TOKENS["CUSTOMER_BID"]`, so the placeholder panel never offers them, and a
hand-typed `{margin}` renders as literal text rather than a real number.
That is the whole defense, and it is enough given every admin is an employee.

---

## 12. Port checklist

**Copy essentially verbatim** (rename `capexflow-` → `bidflow-`, retitle
strings):

- `services/email_frame.py` — plus the `audience` parameter from §5.3
- `services/email_outlook.py` — plus `reply_to` from §7.3
- `services/settings_service.py` — the mode/recipient half
- `services/notify.py` — `_delivery`, `_emit`, `_send_template`, `_emit_plain`;
  `_emit`/`_send_template` gain the `recipient_kind`, `audience`, and
  `reply_to` pass-throughs and hand them to `wrap()` and the transport
- `blueprints/email_templates.py` — all seven endpoints
- `schemas/email_template.py`
- `api/emailTemplates.ts`, `EmailTemplatesPage.tsx`,
  `EmailTemplateEditor.tsx`, `EmailDeliveryMode.tsx`, `QuillEditor.tsx`
- `email-rounded-corners-guide.md` itself

**Rewrite for the bid domain:**

- `TYPES`, `NAMES`, `TOKENS`, `DEFAULTS`, `BUTTONS`, `AUDIENCE` in
  `email_template_service.py` / `email_frame.py` — §5.2 and §6
- `context_for()` and `sample_context()` — §4.1
- the `notify_*` functions, one per type — §6.1
- `NotificationLog` with `bid_id` + `recipient_kind` — §3
- the brand PNGs, via the Pillow generator

**Do not copy:**

- `EmailSettingsIn`'s raising validator — §9.2
- the broken `ValidationError` handler — fix it while porting

**Build order:** frame + PNGs + parity test → template service with defaults →
notify + delivery mode → admin API → editor UI → customer send last, once the
Test-mode rail is proven.

---

## Open questions

- **Server transport.** Outlook COM only works while the app runs on a Windows
  desktop with Outlook installed. Moving to a server means SMTP or Microsoft
  Graph. The one-file boundary makes it cheap, but Graph needs an Azure app
  registration — worth starting that conversation before the bid app goes
  multi-user, not after.
- **Quote expiry reminders.** A bid has `valid_until`; CAPEX Flow has no
  scheduled email at all and therefore no scheduler. If expiry reminders are
  wanted, they need one — out of scope here, and a reason not to assume every
  email is transition-triggered forever.
