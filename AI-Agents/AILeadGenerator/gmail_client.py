import base64
import http.server
import os
import urllib.parse
import webbrowser
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

_SCOPES     = ["https://www.googleapis.com/auth/gmail.send"]
_DIR        = os.path.dirname(os.path.abspath(__file__))
_TOKEN_PATH = os.path.join(_DIR, "credentials", "token.json")
_CREDS_PATH = os.path.join(_DIR, "credentials", "credentials.json")
_PORT       = 8080


class GmailClient:
    def __init__(self, sender_email: str):
        self.sender = sender_email
        self.service = self._authenticate()

    def send_email(self, to: str, subject: str, body: str, html: str | None = None) -> bool:
        try:
            if html:
                msg = MIMEMultipart("alternative")
                msg.attach(MIMEText(body, "plain", "utf-8"))
                msg.attach(MIMEText(html, "html", "utf-8"))
            else:
                msg = MIMEText(body, "plain", "utf-8")

            msg["to"] = to
            msg["from"] = self.sender
            msg["subject"] = subject
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            self.service.users().messages().send(userId="me", body={"raw": raw}).execute()
            return True
        except Exception as e:
            print(f"  [Gmail] Send failed: {e}")
            return False

    # ------------------------------------------------------------------

    def _authenticate(self):
        creds = None

        if os.path.exists(_TOKEN_PATH):
            creds = Credentials.from_authorized_user_file(_TOKEN_PATH, _SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(_CREDS_PATH):
                    raise FileNotFoundError(
                        f"Gmail credentials not found at '{_CREDS_PATH}'. "
                        "See README for setup instructions."
                    )
                creds = self._run_oauth_flow()

            os.makedirs(os.path.join(_DIR, "credentials"), exist_ok=True)
            with open(_TOKEN_PATH, "w") as f:
                f.write(creds.to_json())

        return build("gmail", "v1", credentials=creds)

    @staticmethod
    def _run_oauth_flow() -> Credentials:
        flow = InstalledAppFlow.from_client_secrets_file(_CREDS_PATH, _SCOPES)
        flow.redirect_uri = f"http://localhost:{_PORT}/"

        auth_url, _ = flow.authorization_url(prompt="consent")

        # Capture the OAuth callback via a minimal one-shot HTTP server.
        # The server is bound and ready BEFORE the browser is opened,
        # so the redirect can never arrive before we're listening.
        callback: dict = {}

        class _Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                callback["code"]  = (qs.get("code")  or [None])[0]
                callback["error"] = (qs.get("error") or [None])[0]
                body = b"<html><body><h2>Authorisation complete. You may close this tab.</h2></body></html>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_):
                pass  # suppress request logs

        # SO_REUSEADDR avoids "address already in use" if the port was recently used
        http.server.HTTPServer.allow_reuse_address = True
        server = http.server.HTTPServer(("localhost", _PORT), _Handler)

        print(f"\n{'─' * 60}")
        print("Gmail authorisation required (one-time setup).")
        print(f"Listening on http://localhost:{_PORT}/")
        print()
        print("If the browser does not open, paste this URL manually:")
        print(f"\n  {auth_url}\n")
        print(f"{'─' * 60}\n")

        # Browser opens only after server is bound and listening
        webbrowser.open(auth_url)

        # Block until exactly one request arrives (the OAuth redirect)
        server.handle_request()
        server.server_close()

        if callback.get("error"):
            raise RuntimeError(f"OAuth error: {callback['error']}")
        if not callback.get("code"):
            raise RuntimeError("No authorisation code received — did you complete the browser flow?")

        flow.fetch_token(code=callback["code"])
        return flow.credentials
