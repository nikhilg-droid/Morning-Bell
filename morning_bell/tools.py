"""The four tools Morning Bell's AI can call.

1. search_college_emails  - find new college emails in Gmail
2. read_email             - open one email and get its full text
3. create_calendar_event  - add a class/exam/deadline to Google Calendar with alerts
4. send_morning_digest    - email the student a summary of today's schedule changes
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import config

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_college_emails",
            "description": (
                "Search the student's Gmail for recent college emails that have not been processed yet. "
                "Returns id, sender, subject, date and a short snippet for each email. "
                "Call this first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "extra_query": {
                        "type": "string",
                        "description": "Optional extra Gmail search terms, e.g. 'exam OR quiz'. Leave empty for all college mail.",
                    },
                    "max_results": {"type": "integer", "description": "Max emails to return (1-30). Default 15."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_email",
            "description": (
                "Read the full body of one email by its id. Use it on every email whose snippet might "
                "mention a class, lab, exam, quiz, assignment deadline, event, reschedule or cancellation."
            ),
            "parameters": {
                "type": "object",
                "properties": {"message_id": {"type": "string", "description": "Email id from search_college_emails."}},
                "required": ["message_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": (
                "Add one schedule item to Google Calendar with alerts. Use for classes, rescheduled lectures, "
                "exams, quizzes, labs, assignment deadlines and college events. Skips duplicates automatically. "
                "For a deadline with no duration, use a 30-minute event ending at the deadline."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Short title, e.g. 'DBMS Mid-Sem Exam' or 'OS Assignment 3 due'."},
                    "category": {
                        "type": "string",
                        "enum": ["class", "reschedule", "cancellation", "exam", "deadline", "event", "other"],
                    },
                    "start": {"type": "string", "description": "Start in local time, ISO format YYYY-MM-DDTHH:MM."},
                    "end": {"type": "string", "description": "End in local time, ISO format YYYY-MM-DDTHH:MM."},
                    "location": {"type": "string", "description": "Room / venue / meeting link, if given."},
                    "details": {"type": "string", "description": "1-3 lines: what to bring, syllabus, instructions."},
                    "source_email_id": {"type": "string", "description": "id of the email this came from."},
                    "reminder_minutes": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Minutes before start to alert. Default [1440, 60] for exams/deadlines, [30] for classes.",
                    },
                },
                "required": ["title", "category", "start", "end"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_morning_digest",
            "description": (
                "Send the student ONE morning summary email. Call this last, exactly once, after all calendar "
                "events are created. Include items with no fixed time (notices, cancellations, general info) too."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "headline": {"type": "string", "description": "One-line summary, e.g. '2 exams this week, 1 class cancelled'."},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "when": {"type": "string", "description": "e.g. 'Tue 26 Nov, 10:00' or 'No date'"},
                                "what": {"type": "string"},
                                "category": {"type": "string"},
                                "added_to_calendar": {"type": "boolean"},
                            },
                            "required": ["when", "what", "category", "added_to_calendar"],
                        },
                    },
                },
                "required": ["headline", "items"],
            },
        },
    },
]

CATEGORY_COLORS = {  # Google Calendar colorId
    "exam": "11", "deadline": "6", "reschedule": "5", "cancellation": "8",
    "class": "9", "event": "10", "other": "1",
}


class ToolBox:
    def __init__(self, backend) -> None:
        self.backend = backend
        self.tz = ZoneInfo(config.TIMEZONE)
        self.log: list[str] = []
        self.calendar_items = 0  # events created (or found already on calendar) this run

    # 1
    def search_college_emails(self, extra_query: str = "", max_results: int = 15) -> dict:
        max_results = max(1, min(int(max_results or 15), 30))
        days = max(1, -(-config.LOOKBACK_HOURS // 24))
        query = f"{config.COLLEGE_QUERY} newer_than:{days}d -label:{config.PROCESSED_LABEL.replace(' ', '-')}"
        if extra_query:
            query += f" ({extra_query})"
        emails = self.backend.search_emails(query, max_results)
        return {"query": query, "count": len(emails), "emails": emails}

    # 2
    def read_email(self, message_id: str) -> dict:
        return self.backend.read_email(message_id)

    # 3
    def create_calendar_event(
        self, title: str, category: str, start: str, end: str,
        location: str = "", details: str = "", source_email_id: str = "",
        reminder_minutes: list[int] | None = None,
    ) -> dict:
        start_dt = self._parse(start)
        end_dt = self._parse(end)
        if end_dt <= start_dt:
            end_dt = start_dt + timedelta(minutes=30)
        if end_dt < datetime.now(self.tz) - timedelta(hours=1):
            return {"status": "skipped", "reason": "event is in the past"}

        if self.backend.find_event(title, start_dt.isoformat()):
            self.calendar_items += 1
            return {"status": "skipped", "reason": "already on calendar"}

        if not reminder_minutes:
            reminder_minutes = [1440, 60] if category in ("exam", "deadline") else [30]
        reminders = [{"method": "popup", "minutes": int(m)} for m in reminder_minutes[:4]]
        if category in ("exam", "deadline"):
            reminders.append({"method": "email", "minutes": 1440})

        prefix = {"cancellation": "[CANCELLED] ", "reschedule": "[RESCHEDULED] "}.get(category, "")
        for word in ("(Cancelled)", "(Rescheduled)", "Cancelled", "Rescheduled"):
            if prefix and title.lower().endswith(word.lower()):
                title = title[: -len(word)].rstrip(" -–(")
        description = details
        if source_email_id:
            description += f"\n\nFrom college email (Gmail id {source_email_id}). Added by Morning Bell."
        body = {
            "summary": prefix + title,
            "location": location,
            "description": description.strip(),
            "start": {"dateTime": start_dt.isoformat(), "timeZone": config.TIMEZONE},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": config.TIMEZONE},
            "colorId": CATEGORY_COLORS.get(category, "1"),
            "reminders": {"useDefault": False, "overrides": reminders},
        }
        result = self.backend.create_event(body)
        self.calendar_items += 1
        self.log.append(f"Calendar: {body['summary']} @ {start_dt:%a %d %b %H:%M}")
        return {"status": "created", **result, "alerts_minutes_before": [r["minutes"] for r in reminders]}

    # 4
    def send_morning_digest(self, headline: str, items: list[dict]) -> dict:
        claimed = sum(1 for i in items if i.get("added_to_calendar"))
        if claimed > self.calendar_items:
            return {
                "error": f"{claimed} items are marked added_to_calendar, but only {self.calendar_items} events "
                         "were created with create_calendar_event. Call create_calendar_event for each dated "
                         "item first, then send the digest."
            }
        today = datetime.now(self.tz).strftime("%A, %d %B")
        rows = "".join(
            f"<tr><td style='padding:6px 10px'>{i.get('when','')}</td>"
            f"<td style='padding:6px 10px'><b>{i.get('category','').title()}</b></td>"
            f"<td style='padding:6px 10px'>{i.get('what','')}</td>"
            f"<td style='padding:6px 10px'>{'📅 added' if i.get('added_to_calendar') else '—'}</td></tr>"
            for i in items
        ) or "<tr><td colspan=4 style='padding:6px 10px'>No schedule changes today. 🎉</td></tr>"
        html = (
            f"<p style='font-size:16px'>🔔 <b>{headline}</b></p>"
            "<table style='border-collapse:collapse;font-family:sans-serif;font-size:14px' border='1'>"
            "<tr style='background:#f3f3f3'><th>When</th><th>Type</th><th>What</th><th>Calendar</th></tr>"
            f"{rows}</table><p style='color:#888;font-size:12px'>Sent by Morning Bell</p>"
        )
        result = self.backend.send_email(f"🔔 Morning Bell — {today}", html)
        self.log.append(f"Digest sent: {headline}")
        return {"status": "sent", **result}

    # ---------- helpers ----------
    def _parse(self, value: str) -> datetime:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return dt.replace(tzinfo=self.tz) if dt.tzinfo is None else dt.astimezone(self.tz)

    def call(self, name: str, args: dict):
        fn = {
            "search_college_emails": self.search_college_emails,
            "read_email": self.read_email,
            "create_calendar_event": self.create_calendar_event,
            "send_morning_digest": self.send_morning_digest,
        }.get(name)
        if fn is None:
            raise ValueError(f"Unknown tool {name}")
        return fn(**args)
