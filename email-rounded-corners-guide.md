# Rounded corners in HTML email (Outlook-proof)

A portable recipe for brand-framed notification emails whose rounded corners
survive **classic Outlook desktop**. Extracted from the CAPRI app
(United Uptime Services), where it was iterated against real Outlook renders
until it was pixel-stable. Drop this file into any project that sends HTML
email and follow the recipe.

---

## 1. Why your corners keep coming out square

Classic Outlook (desktop, Windows) renders HTML email with **Microsoft
Word's engine**, not a browser. Word's engine:

- **Ignores `border-radius` entirely.** No CSS trick fixes this.
- **Mangles VML on send.** The classic "VML roundrect fallback" renders in
  *your* Outlook preview, but when Outlook *sends* the message it rewrites
  the HTML and corrupts the VML — recipients get garbage. Don't use VML for
  anything that goes through an Outlook sender.
- Ignores `div`-based layout, `max-width`, and padding on `<a>` tags.
- **Renders images perfectly.**

So: any corner that must look rounded in classic Outlook has to be **baked
into an image**. Keep `border-radius` in your CSS if you like — capable
clients (Gmail, Apple Mail, Outlook on the web) will honor it and Outlook
desktop degrades to square — but for chrome where rounded corners are
non-negotiable, images are the only reliable answer.

## 2. The recipe

Structure every email as a **640px table** with three image-backed pieces:

```
┌──────────────────────────────────────┐
│  header PNG (640×85)                 │  ← navy band, logo + wordmark,
│  rounded TOP corners baked in        │    top-left/right radius in the pixels
├──────────────────────────────────────┤
│  white <td>, inline-CSS body text    │  ← the editable message body
│  [ CTA button PNG, wrapped in <a> ]  │  ← rounded button baked into a PNG
├──────────────────────────────────────┤
│  footer <td> (small gray text)       │
├──────────────────────────────────────┤
│  bottom PNG (640×14)                 │  ← white strip, rounded BOTTOM
│  rounded BOTTOM corners baked in     │    corners baked in
└──────────────────────────────────────┘
        page background: light tint (#EEF3FB)
```

Rules that made it work:

1. **Tables only, inline CSS only.** `role="presentation"`,
   `cellpadding="0" cellspacing="0"`, background colors via `bgcolor` on
   `<td>` (not CSS `background`).
2. **Render PNGs at 2x, display at 1x.** A 640-wide header is a
   1280px-wide PNG with `width="640" height="85"` attributes on the `<img>`.
   Crisp on high-DPI screens; Outlook respects the HTML width/height
   attributes.
3. **Every `<img>` gets** `width`/`height` **attributes** (display size, not
   pixel size), `style="display:block;border:0;"`, and meaningful `alt` text.
   `display:block` kills the mystery gap under images; `alt` covers
   images-blocked clients.
4. **Buttons are images wrapped in a plain `<a>`.** Word ignores padding on
   `<a>`, so CSS "bulletproof buttons" collapse; a rounded PNG with the label
   baked in cannot. One PNG per button variant.
5. **The rounded corners work because the email's outer background is a flat
   solid color** (here `#EEF3FB`). The PNG's corners are transparent (or
   filled with that same tint), so the band appears rounded against the
   backdrop. Keep the backdrop a solid color — a gradient or image would
   betray the rectangle.
6. **Send the same markup to every client.** Don't branch per client; one
   table+image layout renders acceptably everywhere.

## 3. Reference markup (the frame)

This is the production frame, genericized. Replace `{{...}}` placeholders.
`src` values are `cid:` references — see §5 for how those get attached.

```html
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#EEF3FB">
  <tr><td align="center" style="padding:24px;">
    <table role="presentation" width="640" cellpadding="0" cellspacing="0">
      <!-- rounded header band: logo, wordmark, and top corner radius are IN the PNG -->
      <tr><td>
        <img src="cid:myapp-header" width="640" height="85"
             alt="{{Company — App Name}}" style="display:block;border:0;">
      </td></tr>
      <!-- body -->
      <tr><td bgcolor="#ffffff"
              style="padding:24px 28px;font:15px/1.5 Arial,Helvetica,sans-serif;color:#0B1B2B;">
        {{body_html}}
        <!-- CTA button: rounded corners + label baked into the PNG -->
        <table role="presentation" cellpadding="0" cellspacing="0" style="margin:20px 0 4px;">
          <tr><td>
            <a href="{{action_url}}">
              <img src="cid:myapp-btn-primary" width="173" height="44"
                   alt="{{Open the request}}" style="display:block;border:0;">
            </a>
          </td></tr>
        </table>
      </td></tr>
      <!-- footer -->
      <tr><td bgcolor="#ffffff"
              style="padding:16px 28px;border-top:1px solid #E2E8F0;font:12px Arial,Helvetica,sans-serif;color:#64748B;">
        Automated message from {{App Name}} — please do not reply.
      </td></tr>
      <!-- rounded bottom strip: bottom corner radius is IN the PNG -->
      <tr><td>
        <img src="cid:myapp-bottom" width="640" height="14"
             alt="" style="display:block;border:0;">
      </td></tr>
    </table>
  </td></tr>
</table>
```

Asset inventory used by the source app (display size — PNGs are 2x):

| Asset            | Display size | Pixel size | Contents                                   |
|------------------|--------------|------------|--------------------------------------------|
| header           | 640×85       | 1280×170   | navy band, logo, wordmark, rounded top     |
| bottom           | 640×14       | 1280×28    | white strip, rounded bottom corners        |
| button (per CTA) | ~160–250×44  | 2x that    | blue pill, white label text, fully rounded |

## 4. Generating the PNGs (Pillow)

The source app's assets were produced as static files; here is an equivalent
generator so the other project can make its own. Requires `pip install pillow`
and a `.ttf` for the label/wordmark (Arial shown; any brand font works).

```python
"""Generate rounded email chrome PNGs at 2x. Run once, commit the PNGs."""
from PIL import Image, ImageDraw, ImageFont

S = 2  # supersample factor: draw at 2x display size
NAVY, BLUE, WHITE, PAGE = "#0B2A4A", "#2563EB", "#ffffff", "#EEF3FB"
FONT = "arial.ttf"       # swap for your brand font file
RADIUS = 12 * S          # corner radius at 2x


def header(path, w=640, h=85, title="APP NAME"):
    img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))  # transparent corners
    d = ImageDraw.Draw(img)
    # round only the TOP corners: rounded rect, then square off the bottom edge
    d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=RADIUS, fill=NAVY)
    d.rectangle([0, h * S - RADIUS, w * S - 1, h * S - 1], fill=NAVY)
    d.text((28 * S, h * S // 2), title, font=ImageFont.truetype(FONT, 22 * S),
           fill=WHITE, anchor="lm")
    img.save(path)


def bottom(path, w=640, h=14):
    img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # round only the BOTTOM corners
    d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=RADIUS, fill=WHITE)
    d.rectangle([0, 0, w * S - 1, RADIUS], fill=WHITE)
    img.save(path)


def button(path, label, h=44, pad=24):
    font = ImageFont.truetype(FONT, 15 * S)
    text_w = ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(label, font=font)
    w2 = int(text_w) + 2 * pad * S
    img = Image.new("RGBA", (w2, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w2 - 1, h * S - 1], radius=h * S // 2, fill=BLUE)
    d.text((w2 // 2, h * S // 2), label, font=font, fill=WHITE, anchor="mm")
    img.save(path)
    print(f"{path}: display width={w2 // S}, height={h}")  # use in <img> attrs


header("email_header.png")
bottom("email_bottom.png")
button("email_btn_primary.png", "Open the request")
```

The button generator prints the **display** width — put that (not the pixel
width) in the `<img width=...>` attribute, with `height="44"`.

## 5. Delivering the images inline (Content-ID)

The HTML references `cid:myapp-header` etc.; the sender must attach each
referenced PNG with a matching **Content-ID**. Never hotlink from a web
server (blocked-by-default in most clients) and never rely on base64 `data:`
URIs in the sent mail (Outlook strips them).

**Outlook COM (what the source app uses on Windows):**

```python
import re, os
import win32com.client, pythoncom

CID_RE = re.compile(r"cid:(myapp-[a-z0-9-]+)")
ASSETS = {"myapp-header": "email_header.png",
          "myapp-bottom": "email_bottom.png",
          "myapp-btn-primary": "email_btn_primary.png"}
PR_ATTACH_CONTENT_ID = "http://schemas.microsoft.com/mapi/proptag/0x3712001F"

def send(to, subject, html, assets_dir):
    pythoncom.CoInitialize()
    try:
        mail = win32com.client.Dispatch("Outlook.Application").CreateItem(0)
        mail.To, mail.Subject = to, subject
        for cid in sorted(set(CID_RE.findall(html))):      # attach only what's referenced
            att = mail.Attachments.Add(os.path.join(assets_dir, ASSETS[cid]))
            att.PropertyAccessor.SetProperty(PR_ATTACH_CONTENT_ID, cid)
        mail.HTMLBody = html
        mail.Send()
    finally:
        pythoncom.CoUninitialize()
```

**SMTP (smtplib / email.message):**

```python
from email.message import EmailMessage

msg = EmailMessage()
msg["To"], msg["From"], msg["Subject"] = to, sender, subject
msg.set_content("HTML email — open in an HTML-capable client.")
msg.add_alternative(html, subtype="html")
for cid, filename in assets_used.items():                 # cid without <> here
    with open(filename, "rb") as f:
        msg.get_payload()[1].add_related(
            f.read(), maintype="image", subtype="png", cid=f"<{cid}>")
```

**Microsoft Graph:** add each PNG as a `fileAttachment` with
`"isInline": true` and `"contentId": "myapp-header"`.

## 6. Preview parity (worth stealing)

The source app renders in-app previews with **the exact same frame function**,
swapping the `src` resolver: sent mail gets `cid:` URIs, the browser preview
gets `data:` URIs of the same PNGs. A unit test pins preview HTML == sent HTML
(modulo the src scheme), so what admins see in the template editor is what
Outlook receives. If your app previews emails, parameterize the image `src`
the same way instead of maintaining two templates.

## 7. Checklist / gotchas

- [ ] `border-radius` nowhere load-bearing; every must-be-rounded corner is in a PNG.
- [ ] No VML anywhere (it breaks on *send* through Outlook, not just render).
- [ ] Tables + inline CSS only; `bgcolor` on `<td>`; no `<div>` layout, no `<style>` block reliance.
- [ ] Every `<img>`: `width`/`height` attrs at display size, `style="display:block;border:0;"`, `alt`.
- [ ] PNGs at 2x for high-DPI; transparent corners over a solid page background color.
- [ ] Buttons = image inside `<a>`; never padding-on-`<a>`.
- [ ] Inline images attached by Content-ID, attaching only the assets the HTML references.
- [ ] Verify against a **real classic-Outlook render** (send a sample to yourself), not just a browser — the browser lies about everything above.
