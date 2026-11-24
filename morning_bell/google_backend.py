"""Gmail + Google Calendar access.

`GoogleBackend` talks to the real Google APIs (OAuth on first run).
`DemoBackend` uses sample emails and an in-memory calendar so you can try the
agent without connecting a Google account.
"""
from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from html import unescape

from . import config

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",    # read mail, add labels, send digest
    "https://www.googleapis.com/auth/calendar.events",  # create events with reminders
]


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", html)
    text = unescape(re.sub(r"<[^>]+>", " ", html))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n\n", text)).strip()


class GoogleBackend:
    def __init__(self) -> None:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds = None
        if config.TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(config.TOKEN_FILE), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not config.CREDENTIALS_FILE.exists():
                    raise SystemExit(
                        f"Missing {config.CREDENTIALS_FILE.name}. See README: 'Google setup'."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(config.CREDENTIALS_FILE), SCOPES)
                creds = flow.run_local_server(port=0)
            config.TOKEN_FILE.write_text(creds.to_json())

        self.gmail = build("gmail", "v1", credentials=creds)
        self.calendar = build("calendar", "v3", credentials=creds)
        self._label_id: str | None = None

    # ---------- Gmail ----------
    def _processed_label_id(self) -> str:
        if self._label_id:
            return self._label_id
        labels = self.gmail.users().labels().list(userId="me").execute().get("labels", [])
        for lab in labels:
            if lab["name"] == config.PROCESSED_LABEL:
                self._label_id = lab["id"]
                return self._label_id
        created = self.gmail.users().labels().create(
            userId="me", body={"name": config.PROCESSED_LABEL}
        ).execute()
        self._label_id = created["id"]
        return self._label_id

    def search_emails(self, query: str, max_results: int) -> list[dict]:
        resp = self.gmail.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()
        out = []
        for m in resp.get("messages", []):
            msg = self.gmail.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
            out.append({
                "id": m["id"],
                "from": headers.get("From", ""),
                "subject": headers.get("Subject", ""),
                "date": headers.get("Date", ""),
                "snippet": unescape(msg.get("snippet", "")),
            })
        return out

    def read_email(self, message_id: str) -> dict:
        msg = self.gmail.users().messages().get(userId="me", id=message_id, format="full").execute()
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        plain, html, attachments = [], [], []

        def walk(part):
            mime = part.get("mimeType", "")
            data = part.get("body", {}).get("data")
            if part.get("filename"):
                attachments.append(part["filename"])
            elif data and mime == "text/plain":
                plain.append(base64.urlsafe_b64decode(data).decode("utf-8", "replace"))
            elif data and mime == "text/html":
                html.append(base64.urlsafe_b64decode(data).decode("utf-8", "replace"))
            for p in part.get("parts", []) or []:
                walk(p)

        walk(msg["payload"])
        body = "\n".join(plain) if plain else _html_to_text("\n".join(html))
        # Mark as processed so tomorrow's run skips it.
        self.gmail.users().messages().modify(
            userId="me", id=message_id, body={"addLabelIds": [self._processed_label_id()]}
        ).execute()
        return {
            "id": message_id,
            "from": headers.get("From", ""),
            "subject": headers.get("Subject", ""),
            "date": headers.get("Date", ""),
            "body": body[:8000],
            "attachments": attachments,
        }

    def send_email(self, subject: str, body_html: str) -> dict:
        to = config.DIGEST_TO or self.gmail.users().getProfile(userId="me").execute()["emailAddress"]
        mime = MIMEText(body_html, "html")
        mime["to"] = to
        mime["subject"] = subject
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        sent = self.gmail.users().messages().send(userId="me", body={"raw": raw}).execute()
        return {"sent_to": to, "message_id": sent["id"]}

    # ---------- Calendar ----------
    def find_event(self, title: str, start_iso: str) -> dict | None:
        start = datetime.fromisoformat(start_iso)
        if start.tzinfo is None:
            from zoneinfo import ZoneInfo
            start = start.replace(tzinfo=ZoneInfo(config.TIMEZONE))
        resp = self.calendar.events().list(
            calendarId=config.CALENDAR_ID,
            timeMin=(start - timedelta(minutes=1)).isoformat(),
            timeMax=(start + timedelta(minutes=1)).isoformat(),
            singleEvents=True,
        ).execute()
        for ev in resp.get("items", []):
            if ev.get("summary", "").strip().lower() == title.strip().lower():
                return ev
        return None

    def create_event(self, body: dict) -> dict:
        ev = self.calendar.events().insert(calendarId=config.CALENDAR_ID, body=body).execute()
        return {"event_id": ev["id"], "link": ev.get("htmlLink")}


class DemoBackend:
    """Offline stand-in: sample college emails, prints instead of writing to Google."""

    def __init__(self) -> None:
        from .sample_emails import build
        self.emails = {e["id"]: e for e in build()}
        self.events: list[dict] = []
        self.sent: list[dict] = []

    def search_emails(self, query: str, max_results: int) -> list[dict]:
        return [
            {k: e[k] for k in ("id", "from", "subject", "date")} | {"snippet": e["body"][:140]}
            for e in list(self.emails.values())[:max_results]
        ]

    def read_email(self, message_id: str) -> dict:
        if message_id not in self.emails:
            raise ValueError(f"No email with id {message_id}")
        return self.emails[message_id] | {"attachments": []}

    def find_event(self, title: str, start_iso: str) -> dict | None:
        for ev in self.events:
            if ev["summary"].lower() == title.lower() and ev["start"].get("dateTime", "").startswith(start_iso[:16]):
                return ev
        return None

    def create_event(self, body: dict) -> dict:
        body = body | {"id": f"demo-{len(self.events) + 1}"}
        self.events.append(body)
        return {"event_id": body["id"], "link": None}

    def send_email(self, subject: str, body_html: str) -> dict:
        self.sent.append({"subject": subject, "body": body_html})
        out = config.ROOT / "demo_digest.html"
        out.write_text(f"<h2>{subject}</h2>\n{body_html}")
        return {"sent_to": "(demo) saved to demo_digest.html", "message_id": "demo"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
