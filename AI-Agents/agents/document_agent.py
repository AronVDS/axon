"""
DocumentAgent — generates PDF and TXT documents using Ollama llama3.
Actions: offerte, weekrapport, email, samenvatting
Saves to docs/ folder.
"""

import csv
import json
import os
import re
from datetime import date, datetime, timedelta

import ollama
from fpdf import FPDF

_THIS_DIR   = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR   = os.path.normpath(os.path.join(_THIS_DIR, ".."))
_DOCS_DIR   = os.path.join(_ROOT_DIR, "docs")
_TASKS_PATH = os.path.join(_ROOT_DIR, "tasks.json")
_LEADS_PATH = os.path.join(_ROOT_DIR, "AILeadGenerator", "leads.csv")

os.makedirs(_DOCS_DIR, exist_ok=True)

_GREEN = (46, 125, 50)
_DARK  = (30, 30, 30)
_GREY  = (120, 120, 120)
_LIGHT = (245, 245, 245)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _safe(text: str) -> str:
    """Encode to Windows-1252 for PDF core fonts (covers all Dutch characters)."""
    return text.encode("cp1252", errors="replace").decode("cp1252")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower())[:30].strip("_")


def _today_str() -> str:
    return date.today().strftime("%Y%m%d")


def _next_offerte_nr() -> str:
    count = sum(1 for f in os.listdir(_DOCS_DIR) if f.startswith("offerte_"))
    return f"AXON-{date.today().strftime('%Y%m%d')}-{count + 1:03d}"


def _valid_until(geldigheid: str) -> str:
    try:
        days = int(re.search(r"\d+", geldigheid).group())
    except (AttributeError, ValueError):
        days = 30
    return (date.today() + timedelta(days=days)).strftime("%d/%m/%Y")


# ---------------------------------------------------------------------------
# Ollama helpers
# ---------------------------------------------------------------------------

_NL_SYSTEM = (
    "Je bent een professionele schrijver voor Axon, een AI-bureau voor Belgische KMO's. "
    "Schrijf altijd in het Nederlands. Wees professioneel, beknopt en zakelijk."
)


def _llm(user: str, system: str = _NL_SYSTEM) -> str:
    return ollama.chat(
        model="llama3",
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    )["message"]["content"].strip()


def _llm_json(user: str, retries: int = 3) -> dict | None:
    for attempt in range(retries):
        raw     = _llm(user)
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
        match   = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        if attempt < retries - 1:
            print(f"  [DocumentAgent] JSON parse mislukt (poging {attempt + 1}/{retries}), opnieuw...")
    return None


# ---------------------------------------------------------------------------
# Data readers
# ---------------------------------------------------------------------------

def _read_tasks() -> list[dict]:
    if not os.path.exists(_TASKS_PATH):
        return []
    with open(_TASKS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _read_leads() -> list[dict]:
    if not os.path.exists(_LEADS_PATH):
        return []
    with open(_LEADS_PATH, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# PDF base class
# ---------------------------------------------------------------------------

class _PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 20)
        self.set_text_color(*_GREEN)
        self.cell(32, 12, "Axon", ln=0)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*_GREY)
        self.cell(
            0, 12,
            f"AI Chief of Staff voor Belgische KMO's    {date.today().strftime('%d/%m/%Y')}",
            ln=1,
        )
        self.set_draw_color(*_GREEN)
        self.set_line_width(0.4)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*_GREY)
        self.cell(
            0, 8,
            f"Axon  |  axon.aiagents@gmail.com  |  Pagina {self.page_no()}",
            align="C",
        )

    def h1(self, text: str) -> None:
        self.ln(2)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*_GREEN)
        self.cell(0, 9, _safe(text), ln=1)
        self.set_draw_color(*_GREEN)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)
        self.set_text_color(*_DARK)

    def h2(self, text: str) -> None:
        self.ln(3)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*_DARK)
        self.cell(0, 7, _safe(text), ln=1)
        self.ln(1)

    def body(self, text: str, size: int = 10) -> None:
        self.set_font("Helvetica", "", size)
        self.set_text_color(*_DARK)
        self.multi_cell(0, 5.5, _safe(text))
        self.ln(2)

    def kv(self, key: str, val: str) -> None:
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*_DARK)
        self.cell(48, 7, _safe(key + ":"), ln=0)
        self.set_font("Helvetica", "", 10)
        self.cell(0, 7, _safe(str(val)), ln=1)

    def tbl_header(self, cols: list[str], widths: list[int]) -> None:
        self.set_fill_color(*_GREEN)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 10)
        for i, (c, w) in enumerate(zip(cols, widths)):
            ln = 1 if i == len(cols) - 1 else 0
            self.cell(w, 8, _safe(c), border=1, fill=True, ln=ln)

    def tbl_row(self, cols: list[str], widths: list[int], shade: bool = False) -> None:
        if shade:
            self.set_fill_color(*_LIGHT)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*_DARK)
        for i, (c, w) in enumerate(zip(cols, widths)):
            ln = 1 if i == len(cols) - 1 else 0
            self.cell(w, 7, _safe(str(c)), border=1, fill=shade, ln=ln)


# ---------------------------------------------------------------------------
# Document generators
# ---------------------------------------------------------------------------

def _offerte_fallback(company: str, services: str, price: str, context: str) -> dict:
    """Template-based fallback when llama3 cannot produce valid JSON."""
    omschrijving = services or context or "de gevraagde diensten"
    return {
        "company":     company or "Geachte klant",
        "intro": (
            f"Hartelijk dank voor uw interesse in de diensten van Axon. "
            f"Hierbij ontvangt u onze offerte voor {omschrijving}. "
            "Wij kijken ernaar uit u te begeleiden in uw AI-traject."
        ),
        "diensten":    omschrijving,
        "totaal":      price or "op aanvraag",
        "betaling":    "50% bij opdracht, 50% bij oplevering",
        "afsluiting": (
            "Wij hopen op een vlotte samenwerking en staan steeds klaar voor eventuele vragen. "
            "Deze offerte is 30 dagen geldig."
        ),
    }


def _gen_offerte(params: dict) -> str:
    company  = params.get("company", "")
    services = params.get("services", "")
    price    = params.get("price", "")
    context  = params.get("context") or params.get("topic", "")

    # Flat JSON — no nested arrays so llama3 stays reliable
    prompt = (
        "Schrijf offerte-inhoud in het Nederlands voor:\n"
        f"Bedrijf: {company or 'de klant'}\n"
        f"Diensten: {services or context or 'AI-diensten'}\n"
        f"Prijs: {price or 'op aanvraag'}\n\n"
        "Geef ALLEEN dit JSON-object terug (geen uitleg, geen markdown):\n"
        '{"company":"bedrijfsnaam","intro":"2-3 zinnen introductie",'
        '"diensten":"opsomming van diensten als tekst, elke dienst op een nieuwe regel",'
        '"totaal":"totaalbedrag als tekst bv EUR 1000",'
        '"betaling":"betalingsvoorwaarden",'
        '"afsluiting":"2 zinnen afsluiting"}'
    )

    print("  Offerte genereren met llama3...")
    data = _llm_json(prompt)

    if not data:
        print("  [DocumentAgent] llama3 JSON mislukt, gebruik fallback template.")
        data = _offerte_fallback(company, services, price, context)
        used_fallback = True
    else:
        # Ensure required keys exist
        for key, default in [
            ("company",    company or "Geachte klant"),
            ("intro",      ""),
            ("diensten",   services or context or ""),
            ("totaal",     price or "op aanvraag"),
            ("betaling",   "50% bij opdracht, 50% bij oplevering"),
            ("afsluiting", ""),
        ]:
            if not data.get(key):
                data[key] = default
        used_fallback = False

    nr   = _next_offerte_nr()
    slug = _slug(data.get("company") or company or "offerte")
    base = os.path.join(_DOCS_DIR, f"offerte_{slug}_{_today_str()}")

    # --- PDF ---
    pdf = _PDF()
    pdf.add_page()
    pdf.h1(f"Offerte {nr}")

    pdf.kv("Aan",        data["company"])
    pdf.kv("Datum",      date.today().strftime("%d/%m/%Y"))
    pdf.kv("Referentie", nr)
    pdf.kv("Geldig tot", (date.today() + timedelta(days=30)).strftime("%d/%m/%Y"))
    pdf.ln(4)

    pdf.h2("Inleiding")
    pdf.body(data["intro"])

    pdf.h2("Diensten")
    pdf.body(data["diensten"])

    pdf.h2("Totaal & Betaling")
    pdf.kv("Totaal (excl. BTW)", data["totaal"])
    pdf.kv("Betalingsvoorwaarden", data["betaling"])

    pdf.h2("Afsluiting")
    pdf.body(data["afsluiting"])
    pdf.body("\nMet vriendelijke groeten,\nHet Axon-team")
    pdf.output(base + ".pdf")

    # --- TXT ---
    txt_lines = [
        f"OFFERTE {nr}",
        f"Datum         : {date.today().strftime('%d/%m/%Y')}",
        f"Aan           : {data['company']}",
        f"Referentie    : {nr}",
        "",
        data["intro"],
        "",
        "DIENSTEN:",
        data["diensten"],
        "",
        f"Totaal        : {data['totaal']}",
        f"Betaling      : {data['betaling']}",
        "",
        data["afsluiting"],
        "",
        "Met vriendelijke groeten,",
        "Het Axon-team",
    ]
    with open(base + ".txt", "w", encoding="utf-8") as f:
        f.write("\n".join(txt_lines))

    source = " (fallback template)" if used_fallback else ""
    return (
        f"Offerte aangemaakt{source}:\n"
        f"  Referentie : {nr}\n"
        f"  Bedrijf    : {data['company']}\n"
        f"  Totaal     : {data['totaal']}\n"
        f"  PDF        : {base}.pdf\n"
        f"  TXT        : {base}.txt"
    )


def _gen_weekrapport(params: dict) -> str:  # noqa: ARG001
    all_tasks = _read_tasks()
    all_leads = _read_leads()
    week_ago  = (date.today() - timedelta(days=7)).isoformat()
    today_iso = date.today().isoformat()

    new_tasks  = [t for t in all_tasks if t.get("created_at", "")[:10] >= week_ago]
    done_tasks = [t for t in all_tasks if t.get("done") and t.get("created_at", "")[:10] >= week_ago]
    open_tasks = [t for t in all_tasks if not t.get("done")]
    overdue    = [t for t in open_tasks if t.get("due_date") and t["due_date"] < today_iso]
    week_leads = [l for l in all_leads if l.get("timestamp", "")[:10] >= week_ago]
    sent_leads = [l for l in week_leads if l.get("status") == "sent"]

    data_summary = (
        f"Periode: {week_ago} tot {today_iso}\n\n"
        f"TAKEN:\n"
        f"  Nieuw aangemaakt : {len(new_tasks)}\n"
        f"  Voltooid         : {len(done_tasks)}\n"
        f"  Openstaand       : {len(open_tasks)}\n"
        f"  Achterstallig    : {len(overdue)}\n"
    )
    if new_tasks:
        data_summary += "Nieuwe taken:\n" + "".join(
            f"  - [{t['priority']}] {t['title']}\n" for t in new_tasks[:10]
        )
    data_summary += (
        f"\nACQUISITIE:\n"
        f"  Emails verstuurd : {len(sent_leads)}\n"
        f"  Totaal in db     : {len(all_leads)}\n"
    )
    if sent_leads:
        data_summary += "Gecontacteerde bedrijven:\n" + "".join(
            f"  - {l['name']} ({l.get('email', '')})\n" for l in sent_leads[:10]
        )

    print("  Weekrapport genereren met llama3...")
    insights = _llm(
        f"Schrijf een professioneel weekrapport (3-4 alinea's) op basis van deze data:\n\n"
        f"{data_summary}\n\n"
        "Bespreek prestaties, openstaande prioriteiten en concrete aanbevelingen voor "
        "volgende week. Schrijf in het Nederlands, zakelijk maar motiverend."
    )

    week_label = f"{week_ago} - {today_iso}"
    base       = os.path.join(_DOCS_DIR, f"weekrapport_{_today_str()}")

    # --- PDF ---
    pdf = _PDF()
    pdf.add_page()
    pdf.h1(f"Weekrapport  {week_label}")

    pdf.h2("Takenoverzicht")
    pdf.tbl_header(["Categorie", "Aantal"], [140, 50])
    for label, val, shade in [
        ("Nieuw aangemaakt",  len(new_tasks),  False),
        ("Voltooid",          len(done_tasks), False),
        ("Nog openstaand",    len(open_tasks), False),
        ("Achterstallig",     len(overdue),    bool(overdue)),
    ]:
        pdf.tbl_row([label, str(val)], [140, 50], shade=shade)

    if open_tasks:
        pdf.ln(3)
        pdf.h2("Openstaande taken")
        pri_sym = {"hoog": "[!]", "normaal": "[ ]", "laag": "[-]"}
        for t in open_tasks[:15]:
            sym = pri_sym.get(t.get("priority", "normaal"), "[ ]")
            due = f"  (vervalt: {t['due_date']})" if t.get("due_date") else ""
            pdf.body(f"{sym} {t['title']}{due}", size=9)

    pdf.h2("Acquisitie (leads)")
    pdf.tbl_header(["Categorie", "Aantal"], [140, 50])
    pdf.tbl_row(["Emails verstuurd deze week", str(len(sent_leads))], [140, 50])
    pdf.tbl_row(["Totaal in database",         str(len(all_leads))],  [140, 50])

    if sent_leads:
        pdf.ln(3)
        pdf.h2("Gecontacteerde bedrijven")
        for l in sent_leads[:10]:
            pdf.body(f"- {l['name']}  {l.get('email', '')}", size=9)

    pdf.h2("AI Analyse & Aanbevelingen")
    pdf.body(insights)
    pdf.output(base + ".pdf")

    # --- TXT ---
    txt_lines = [
        f"WEEKRAPPORT {week_label}",
        f"Gegenereerd op: {date.today().strftime('%d/%m/%Y')}",
        "",
        "TAKEN:",
        f"  Nieuw: {len(new_tasks)}  |  Voltooid: {len(done_tasks)}  "
        f"|  Openstaand: {len(open_tasks)}  |  Achterstallig: {len(overdue)}",
        "",
        "ACQUISITIE:",
        f"  Verstuurd deze week: {len(sent_leads)}  |  Totaal in db: {len(all_leads)}",
        "",
        "AI ANALYSE:",
        insights,
    ]
    with open(base + ".txt", "w", encoding="utf-8") as f:
        f.write("\n".join(txt_lines))

    return (
        f"Weekrapport aangemaakt ({week_label}):\n"
        f"  Taken  : {len(new_tasks)} nieuw, {len(done_tasks)} voltooid, "
        f"{len(open_tasks)} open, {len(overdue)} achterstallig\n"
        f"  Leads  : {len(sent_leads)} verstuurd deze week\n"
        f"  PDF    : {base}.pdf\n"
        f"  TXT    : {base}.txt"
    )


def _gen_email(params: dict) -> str:
    recipient = params.get("recipient") or params.get("company", "")
    context   = params.get("context") or params.get("topic", "")

    prompt = (
        "Schrijf een professionele email in het Nederlands.\n"
        f"Ontvanger: {recipient or '(niet opgegeven)'}\n"
        f"Context: {context or '(geen extra context)'}\n\n"
        "Schrijf de volledige email inclusief een onderwerpregel (begin met 'Onderwerp: ').\n"
        "Sluit af met 'Met vriendelijke groeten,\\nHet Axon-team'.\n"
        "Schrijf ALLEEN de email, geen uitleg erbuiten."
    )

    print("  Email opstellen met llama3...")
    content = _llm(prompt)

    slug = _slug(recipient or context or "email")
    base = os.path.join(_DOCS_DIR, f"email_{slug}_{_today_str()}")

    with open(base + ".txt", "w", encoding="utf-8") as f:
        f.write(content)

    pdf = _PDF()
    pdf.add_page()
    pdf.h1("Email concept")
    if recipient:
        pdf.kv("Aan", recipient)
    pdf.kv("Datum", date.today().strftime("%d/%m/%Y"))
    pdf.ln(3)
    pdf.body(content)
    pdf.output(base + ".pdf")

    return (
        f"Email concept aangemaakt:\n"
        f"  TXT : {base}.txt\n"
        f"  PDF : {base}.pdf\n\n"
        f"--- Inhoud ---\n{content}"
    )


def _gen_samenvatting(params: dict) -> str:
    text = params.get("text") or params.get("topic") or params.get("context", "")
    if not text:
        return "[DocumentAgent] Geen tekst opgegeven om samen te vatten."

    print("  Samenvatting genereren met llama3...")
    summary = _llm(
        f"Vat de volgende tekst samen in het Nederlands. "
        f"Geef een beknopte samenvatting (3-5 bulletpunten of 1 alinea):\n\n{text}"
    )

    slug = _slug(text[:40])
    base = os.path.join(_DOCS_DIR, f"samenvatting_{slug}_{_today_str()}")
    header_line = f"SAMENVATTING — {date.today().strftime('%d/%m/%Y')}"

    with open(base + ".txt", "w", encoding="utf-8") as f:
        f.write(f"{header_line}\n\n{summary}")

    pdf = _PDF()
    pdf.add_page()
    pdf.h1("Samenvatting")
    pdf.kv("Datum", date.today().strftime("%d/%m/%Y"))
    pdf.ln(3)
    pdf.h2("Originele tekst (fragment)")
    pdf.body((text[:500] + "..." if len(text) > 500 else text), size=9)
    pdf.h2("Samenvatting")
    pdf.body(summary)
    pdf.output(base + ".pdf")

    return (
        f"Samenvatting aangemaakt:\n"
        f"  TXT : {base}.txt\n"
        f"  PDF : {base}.pdf\n\n"
        f"--- Samenvatting ---\n{summary}"
    )


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class DocumentAgent:
    def run(self, params: dict) -> str:
        doc_type = (params.get("document_type") or "").lower()

        if doc_type in ("offerte", "quote", "prijsopgave"):
            return _gen_offerte(params)
        if doc_type in ("weekrapport", "rapport", "verslag"):
            return _gen_weekrapport(params)
        if doc_type in ("email", "mail"):
            return _gen_email(params)
        if doc_type in ("samenvatting", "samenvatten", "summary"):
            return _gen_samenvatting(params)

        return (
            f"[DocumentAgent] Onbekend documenttype: {doc_type!r}. "
            "Gebruik 'offerte', 'weekrapport', 'email' of 'samenvatting'."
        )
