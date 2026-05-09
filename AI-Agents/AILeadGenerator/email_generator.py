import html as _html
import json
import re

import ollama

# ---------------------------------------------------------------------------
# Sector lookup — the only llama3 call
# ---------------------------------------------------------------------------

_SECTOR_PROMPT = """\
Geef de Nederlandse sectorbenaming voor het opgegeven bedrijfstype.
Antwoord UITSLUITEND met een JSON-object: {"sector": "..."}
Gebruik de meest gangbare Nederlandse term (één tot drie woorden, kleine letters).
Voorbeelden: advocatenkantoor, restaurant, boekhoudkantoor, IT-bedrijf, kapsalon, marketingbureau."""


def _get_sector(business_type: str, model: str) -> str:
    """Ask llama3 for the correct Dutch sector label. Falls back to business_type."""
    try:
        response = ollama.chat(
            model=model,
            format="json",
            messages=[{
                "role": "user",
                "content": f"Bedrijfstype: {business_type}",
            }],
            system=_SECTOR_PROMPT,
        )
        raw = response["message"]["content"].strip()
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
        data = json.loads(cleaned)
        sector = str(data.get("sector", "")).strip()
        return sector if sector else business_type
    except Exception:
        return business_type


# ---------------------------------------------------------------------------
# Fixed email template
# ---------------------------------------------------------------------------

_SUBJECT = "Axon — minder administratie, meer tijd voor {name}"

_BODY = """\
Beste {name},

Als {sector} kent u de uitdaging van te veel tijd verliezen aan administratie, emails en opvolging. Axon is een AI Chief of Staff die dit voor u overneemt — zodat u zich kan focussen op wat echt telt.

Heeft u 15 minuten om te zien hoe Axon {name} kan helpen?

Met vriendelijke groeten,
Het Axon-team
axon-e6m2.onrender.com"""

# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="margin:0;padding:0;background-color:#f4f4f5;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="background-color:#f4f4f5;padding:32px 16px;">
  <tr><td align="center">
    <table role="presentation" cellpadding="0" cellspacing="0"
           style="width:100%;max-width:540px;">

      <!-- Header -->
      <tr>
        <td align="center"
            style="background-color:#0a0a0f;padding:24px 32px;border-radius:8px 8px 0 0;">
          <span style="font-family:Arial,Helvetica,sans-serif;font-size:22px;
                       font-weight:700;color:#4ade80;letter-spacing:8px;">AXON</span>
        </td>
      </tr>

      <!-- Body -->
      <tr>
        <td style="background-color:#ffffff;padding:32px 32px 28px;
                   font-family:Arial,Helvetica,sans-serif;font-size:15px;
                   line-height:1.75;color:#1a1a1a;">
          {body_html}
        </td>
      </tr>

      <!-- Green accent line -->
      <tr>
        <td style="background-color:#4ade80;height:3px;line-height:3px;
                   font-size:0;mso-line-height-rule:exactly;">&nbsp;</td>
      </tr>

      <!-- Footer -->
      <tr>
        <td align="center"
            style="background-color:#0a0a0f;padding:18px 32px 22px;
                   border-radius:0 0 8px 8px;">
          <p style="margin:0 0 6px;font-family:Arial,Helvetica,sans-serif;
                    font-size:13px;color:#ffffff;">
            AI Chief of Staff voor Belgische KMO&#39;s
          </p>
          <a href="https://axon-e6m2.onrender.com"
             style="font-family:Arial,Helvetica,sans-serif;font-size:12px;
                    color:#4ade80;text-decoration:none;">
            axon-e6m2.onrender.com
          </a>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""


def _text_to_html(text: str) -> str:
    """Convert plain-text email body (\\n\\n paragraphs) to HTML paragraphs."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    parts = []
    for i, para in enumerate(paragraphs):
        margin = "0 0 16px 0" if i < len(paragraphs) - 1 else "0"
        escaped = _html.escape(para).replace("\n", "<br>")
        parts.append(f'<p style="margin:{margin};">{escaped}</p>')
    return "\n          ".join(parts)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class EmailGenerator:
    def __init__(self, model: str = "llama3"):
        self.model = model

    def generate_cold_email(self, business: dict) -> dict:
        name         = business["name"]
        business_type = business.get("type", "bedrijf")

        sector = _get_sector(business_type, self.model)
        print(f"  Sector: {sector!r}")

        plain_body = _BODY.format(name=name, sector=sector)

        body_html = _text_to_html(plain_body).replace(
            "axon-e6m2.onrender.com",
            '<a href="https://axon-e6m2.onrender.com"'
            ' style="color:#4ade80;text-decoration:none;">axon-e6m2.onrender.com</a>',
        )

        return {
            "subject": _SUBJECT.format(name=name),
            "body":    plain_body,
            "html":    _HTML_TEMPLATE.format(body_html=body_html),
        }
