import html as _html
import json
import re

import ollama

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
Je schrijft koude acquisitie-emails namens Axon, een AI Chief of Staff voor Belgische KMO's.
Axon automatiseert administratie, beheert e-mailprioritering, bereidt vergaderingen voor en volgt klanten op.

*** TAAL: SCHRIJF UITSLUITEND IN HET NEDERLANDS. Geen enkel woord Engels. ***

STRIKTE REGELS:
1. Schrijf EXACT 3 korte zinnen — niet meer, niet minder.
2. Wees specifiek voor het type bedrijf (accountantskantoor, marketingbureau, IT-bedrijf, …).
3. Klink menselijk en direct — geen jargon, geen overdreven enthousiasme.
4. Schrijf GEEN aanhef ("Beste …") en GEEN afsluiting ("Met vriendelijke groeten") — die worden automatisch toegevoegd.
5. Geen opsommingen. Geen placeholders. Geen markdown. Geen links.
6. Schrijf in correct, professioneel Nederlands. Gebruik geen neologismen of verzonnen woorden.

OUTPUT: geef ENKEL een JSON-object terug:
{"subject": "...", "body": "..."}

"body" bevat uitsluitend de 3 zinnen, geen aanhef, geen afsluiting."""

def _sanitize_json(s: str) -> str:
    """Escape bare control characters inside JSON string values."""
    result = []
    in_string = False
    escaped = False
    for ch in s:
        if escaped:
            result.append(ch)
            escaped = False
        elif ch == '\\' and in_string:
            result.append(ch)
            escaped = True
        elif ch == '"':
            result.append(ch)
            in_string = not in_string
        elif in_string and ch == '\n':
            result.append('\\n')
        elif in_string and ch == '\r':
            result.append('\\r')
        elif in_string and ch == '\t':
            result.append('\\t')
        else:
            result.append(ch)
    return ''.join(result)

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
        name = business["name"]

        user_msg = (
            f"Schrijf een koude acquisitie-email voor:\n"
            f"- Bedrijfsnaam: {name}\n"
            f"- Type bedrijf: {business.get('type', 'bedrijf')}\n"
            f"- Adres: {business['address']}\n"
        )
        if business.get("website"):
            user_msg += f"- Website: {business['website']}\n"

        response = ollama.chat(
            model=self.model,
            format="json",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
        )

        raw = response["message"]["content"].strip()
        parsed = self._parse(raw, name)

        # Wrap the generated middle with a guaranteed greeting and closing.
        # Doing this in code ensures the business name is always correct and
        # the closing is always present, regardless of what llama3 produced.
        middle = parsed["body"].strip()
        if middle and middle[-1] not in ".!?":
            middle += "."
        parsed["body"] = (
            f"Beste {name},\n\n"
            f"{middle}\n\n"
            f"Met vriendelijke groeten,\n"
            f"Het Axon-team\n"
            f"axon-e6m2.onrender.com"
        )

        # HTML version: replace the plain URL with a styled anchor tag
        body_html = _text_to_html(parsed["body"]).replace(
            "axon-e6m2.onrender.com",
            '<a href="https://axon-e6m2.onrender.com"'
            ' style="color:#4ade80;text-decoration:none;">axon-e6m2.onrender.com</a>',
        )
        parsed["html"] = _HTML_TEMPLATE.format(body_html=body_html)
        return parsed

    # ------------------------------------------------------------------

    @staticmethod
    def _parse(raw: str, company_name: str) -> dict:
        # Strip markdown code fences that llama3 sometimes adds
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()

        # 1. Try parsing the whole cleaned response (with control-char sanitisation)
        try:
            data = json.loads(_sanitize_json(cleaned))
            if "subject" in data and "body" in data:
                return {"subject": str(data["subject"]), "body": str(data["body"])}
        except json.JSONDecodeError:
            pass

        # 2. Find the first {...} block (handles stray text before/after JSON)
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            try:
                data = json.loads(_sanitize_json(match.group()))
                if "subject" in data and "body" in data:
                    return {"subject": str(data["subject"]), "body": str(data["body"])}
            except json.JSONDecodeError:
                pass

        # 3. Last resort: treat entire response as plain body text
        return {
            "subject": f"Axon — AI-ondersteuning voor {company_name}",
            "body": cleaned,
        }
