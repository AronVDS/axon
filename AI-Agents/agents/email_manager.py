"""
EmailManagerAgent — reads, categorises, and replies to Gmail inbox emails.
Uses OAuth 2.0 (gmail.modify scope) + Ollama llama3 for Dutch replies.
"""

import base64
import http.server
import os
import re
import urllib.parse
import webbrowser
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import ollama
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

_THIS_DIR   = os.path.dirname(os.path.abspath(__file__))
_CREDS_DIR  = os.path.normpath(os.path.join(_THIS_DIR, "..", "AILeadGenerator", "credentials"))
_CREDS_PATH = os.path.join(_CREDS_DIR, "credentials.json")
_TOKEN_PATH = os.path.join(_CREDS_DIR, "token_inbox.json")
_SCOPES     = ["https://www.googleapis.com/auth/gmail.modify"]
_PORT       = 8081  # separate port from AILeadGenerator's gmail_client (8080)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def _authenticate():
    creds = None
    if os.path.exists(_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(_TOKEN_PATH, _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(_CREDS_PATH):
                raise FileNotFoundError(
                    f"Gmail credentials niet gevonden op '{_CREDS_PATH}'. "
                    "Zie AILeadGenerator/README.md voor setup."
                )
            creds = _run_oauth_flow()
        os.makedirs(_CREDS_DIR, exist_ok=True)
        with open(_TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def _run_oauth_flow() -> Credentials:
    flow = InstalledAppFlow.from_client_secrets_file(_CREDS_PATH, _SCOPES)
    flow.redirect_uri = f"http://localhost:{_PORT}/"
    auth_url, _ = flow.authorization_url(prompt="consent")
    callback: dict = {}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            callback["code"]  = (qs.get("code")  or [None])[0]
            callback["error"] = (qs.get("error") or [None])[0]
            body = b"<html><body><h2>Klaar. U kunt dit tabblad sluiten.</h2></body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    http.server.HTTPServer.allow_reuse_address = True
    server = http.server.HTTPServer(("localhost", _PORT), _Handler)
    print(f"\n{'─' * 60}")
    print("Gmail-autorisatie vereist voor inbox-toegang (eenmalige setup).")
    print(f"Luisteren op http://localhost:{_PORT}/")
    print("\nAls de browser niet opent, plak deze URL handmatig:")
    print(f"\n  {auth_url}\n")
    print(f"{'─' * 60}\n")
    webbrowser.open(auth_url)
    server.handle_request()
    server.server_close()

    if callback.get("error"):
        raise RuntimeError(f"OAuth fout: {callback['error']}")
    if not callback.get("code"):
        raise RuntimeError("Geen autorisatiecode ontvangen.")

    flow.fetch_token(code=callback["code"])
    return flow.credentials


# ---------------------------------------------------------------------------
# Gmail helpers
# ---------------------------------------------------------------------------

def _extract_body(payload: dict) -> str:
    """Recursively extract readable plain-text body from a Gmail message payload."""
    def _walk(p) -> tuple[str, str]:
        mime = p.get("mimeType", "")
        data = p.get("body", {}).get("data", "")

        if mime == "text/plain" and data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace"), ""

        if mime == "text/html" and data:
            html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            return "", re.sub(r"<[^>]+>", " ", html).strip()

        plain, html = "", ""
        for part in p.get("parts", []):
            pp, ph = _walk(part)
            plain = plain or pp
            html  = html  or ph

        return plain, html

    plain, html = _walk(payload)
    return (plain or html).strip()


def _fetch_emails(service, gmail_query: str, limit: int) -> list[dict]:
    result = service.users().messages().list(
        userId="me", q=gmail_query, maxResults=limit
    ).execute()

    emails = []
    for meta in result.get("messages", []):
        msg  = service.users().messages().get(
            userId="me", id=meta["id"], format="full"
        ).execute()
        hdrs = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        emails.append({
            "id":         msg["id"],
            "thread_id":  msg["threadId"],
            "from":       hdrs.get("From", "(onbekend)"),
            "to":         hdrs.get("To", ""),
            "subject":    hdrs.get("Subject", "(geen onderwerp)"),
            "date":       hdrs.get("Date", ""),
            "message_id": hdrs.get("Message-ID", ""),
            "references": hdrs.get("References", ""),
            "snippet":    msg.get("snippet", ""),
            "body":       _extract_body(msg["payload"]),
        })

    return emails


def _mark_as_read(service, message_id: str) -> None:
    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"removeLabelIds": ["UNREAD"]},
    ).execute()


def _send_reply(service, email: dict, body: str) -> bool:
    try:
        subject = email["subject"]
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"

        msg = MIMEMultipart("alternative")
        msg["To"]          = email["from"]
        msg["Subject"]     = subject
        msg["In-Reply-To"] = email["message_id"]
        msg["References"]  = (email["references"] + " " + email["message_id"]).strip()
        msg.attach(MIMEText(body, "plain", "utf-8"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(
            userId="me",
            body={"raw": raw, "threadId": email["thread_id"]},
        ).execute()
        return True
    except Exception as exc:
        print(f"  [EmailManager] Versturen mislukt: {exc}")
        return False


# ---------------------------------------------------------------------------
# Ollama helpers
# ---------------------------------------------------------------------------

def _categorize(email: dict) -> str:
    response = ollama.chat(
        model="llama3",
        messages=[{
            "role": "user",
            "content": (
                "Categoriseer dit email als één van: lead, client, spam, other.\n\n"
                f"Van: {email['from']}\n"
                f"Onderwerp: {email['subject']}\n"
                f"Inhoud: {email['body'][:500]}\n\n"
                "Antwoord ALLEEN met één woord: lead, client, spam, of other."
            ),
        }],
    )
    raw = response["message"]["content"].strip().lower()
    for cat in ("lead", "client", "spam", "other"):
        if cat in raw:
            return cat
    return "other"


def _generate_reply(email: dict) -> str:
    response = ollama.chat(
        model="llama3",
        messages=[
            {
                "role": "system",
                "content": (
                    "Je bent een professionele assistent voor Axon, een AI-bedrijf voor Belgische KMO's. "
                    "Schrijf antwoorden altijd in het Nederlands. "
                    "Sluit elk antwoord af met: 'Met vriendelijke groeten,\nHet Axon-team'"
                ),
            },
            {
                "role": "user",
                "content": (
                    "Schrijf een kort, professioneel antwoord op dit email. "
                    "Schrijf ALLEEN de inhoud van het antwoord, geen uitleg erbuiten.\n\n"
                    f"Van: {email['from']}\n"
                    f"Onderwerp: {email['subject']}\n"
                    f"Inhoud:\n{email['body'][:1500]}"
                ),
            },
        ],
    )
    return response["message"]["content"].strip()


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class EmailManagerAgent:
    def run(self, params: dict) -> str:
        action = params.get("action", "read")
        query  = params.get("query", "")
        limit  = int(params.get("limit", 10))

        try:
            service = _authenticate()
        except FileNotFoundError as exc:
            return f"[EmailManager] Setup vereist: {exc}"
        except Exception as exc:
            return f"[EmailManager] Authenticatie mislukt: {exc}"

        if action == "read":
            return self._do_read(service, limit, query)
        if action == "categorize":
            return self._do_categorize(service, limit, query)
        if action == "reply":
            return self._do_reply(service, limit, query)

        return (
            f"[EmailManager] Onbekende actie: {action!r}. "
            "Gebruik 'read', 'categorize' of 'reply'."
        )

    # ------------------------------------------------------------------

    def _do_read(self, service, limit: int, query: str) -> str:
        gmail_q = f"is:unread {query}".strip()
        emails  = _fetch_emails(service, gmail_q, limit)
        if not emails:
            return "Geen ongelezen emails gevonden."

        lines = [f"Ongelezen emails ({len(emails)}):"]
        for i, em in enumerate(emails, 1):
            lines += [
                f"\n{i}. Van       : {em['from']}",
                f"   Onderwerp : {em['subject']}",
                f"   Datum     : {em['date']}",
                f"   Preview   : {em['snippet'][:120]}",
            ]
        return "\n".join(lines)

    def _do_categorize(self, service, limit: int, query: str) -> str:
        gmail_q = f"is:unread {query}".strip()
        emails  = _fetch_emails(service, gmail_q, limit)
        if not emails:
            return "Geen ongelezen emails gevonden om te categoriseren."

        counts = {"lead": 0, "client": 0, "spam": 0, "other": 0}
        lines  = [f"Categorisatie van {len(emails)} ongelezen emails:\n"]
        for i, em in enumerate(emails, 1):
            print(f"  Categoriseer: {em['subject'][:60]}...")
            cat = _categorize(em)
            counts[cat] += 1
            lines += [
                f"{i}. [{cat.upper():8}] {em['subject'][:60]}",
                f"   Van: {em['from']}",
            ]

        lines.append(
            f"\nTotaal — Lead: {counts['lead']} | Client: {counts['client']} "
            f"| Spam: {counts['spam']} | Overig: {counts['other']}"
        )
        return "\n".join(lines)

    def _do_reply(self, service, limit: int, query: str) -> str:
        today = date.today().strftime("%Y/%m/%d")
        if "vandaag" in query.lower():
            gmail_q = f"is:unread after:{today}"
        elif query:
            gmail_q = f"is:unread {query}"
        else:
            gmail_q = f"is:unread after:{today}"

        emails = _fetch_emails(service, gmail_q, limit)
        if not emails:
            return "Geen emails gevonden om te beantwoorden."

        sent, failed = 0, 0
        lines = [f"Beantwoorden van {len(emails)} emails:\n"]
        for em in emails:
            print(f"  Genereer antwoord voor: {em['subject'][:60]}...")
            reply = _generate_reply(em)
            ok    = _send_reply(service, em, reply)
            if ok:
                _mark_as_read(service, em["id"])
                sent += 1
                lines += [
                    f"✓ Beantwoord : {em['subject'][:60]}",
                    f"  Aan        : {em['from']}",
                    "",
                ]
            else:
                failed += 1
                lines += [f"✗ Mislukt    : {em['subject'][:60]}", ""]

        lines.append(f"Resultaat: {sent} verstuurd, {failed} mislukt.")
        return "\n".join(lines)
