"""The four tools Morning Bell's AI can call.

1. search_emails          - list every email received in the last 24 hours (Gmail)
2. read_email             - open one email and get its full text
3. create_calendar_event  - add a dated item (meeting, exam, deadline, booking...) to Google Calendar with alerts
4. send_daily_report      - email a categorized report summarizing all of today's mail
"""
from __future__ import annotations

import html as _html
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import config

REPORT_CATEGORIES = [
    "important", "college_work", "personal", "finance", "orders_deliveries", "travel",
    "security_alerts", "social", "newsletters", "promotions", "other",
]
CATEGORY_TITLES = {
    "important": "⭐ Important", "college_work": "🎓 College / Work", "personal": "👋 Personal",
    "finance": "💳 Finance & Bills", "orders_deliveries": "📦 Orders & Deliveries", "travel": "✈️ Travel",
    "security_alerts": "🔐 Security & Accounts", "social": "💬 Social", "newsletters": "📰 Newsletters",
    "promotions": "🏷️ Promotions", "other": "📁 Other",
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_emails",
            "description": (
                "List every email received in the last 24 hours: id, sender, subject, date, Gmail tab "
                "(primary/promotions/social/updates/forums), important/unread flags and a short snippet. Call this first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "extra_query": {
                        "type": "string",
                        "description": "Optional extra Gmail search terms. Leave empty to get all of today's mail.",
                    },
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
                "Read the full body of one email by id. Use it when the snippet is not enough to summarize the "
                "email or to find exact dates/times — e.g. personal or work mail, bills, bookings, meetings, "
                "exams, deadlines. Do NOT read promotions or newsletters; their snippet is enough."
            ),
            "parameters": {
                "type": "object",
                "properties": {"message_id": {"type": "string", "description": "Email id from search_emails."}},
                "required": ["message_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": (
                "Add one dated item to Google Calendar with alerts: meetings, classes, exams, interviews, "
                "appointments, bill/assignment deadlines, travel bookings, events and invitations. Skips duplicates "
                "and past items. For a deadline with no duration, use a 30-minute event ending at the deadline. "
                "Do not add sales/offer expiry dates from promotions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Short title, e.g. 'Electricity bill due' or 'Dinner with Rahul'."},
                    "category": {
                        "type": "string",
                        "enum": ["meeting", "class", "reschedule", "cancellation", "exam", "deadline", "travel", "event", "other"],
                    },
                    "start": {"type": "string", "description": "Start in local time, ISO format YYYY-MM-DDTHH:MM."},
                    "end": {"type": "string", "description": "End in local time, ISO format YYYY-MM-DDTHH:MM."},
                    "location": {"type": "string", "description": "Place / room / meeting link, if given."},
                    "details": {"type": "string", "description": "1-3 lines of useful details."},
                    "source_email_id": {"type": "string", "description": "id of the email this came from."},
                    "reminder_minutes": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Minutes before start to alert. Default [1440, 60] for exams/deadlines/travel, [30] otherwise.",
                    },
                },
                "required": ["title", "category", "start", "end"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_daily_report",
            "description": (
                "Send the user ONE daily email report summarizing ALL emails returned by search_emails. Call it last, "
                "exactly once, after creating calendar events. Every email id from search_emails must appear once in "
                "'emails'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "headline": {"type": "string", "description": "One line, e.g. '34 emails: 2 need action, 1 bill due Friday'."},
                    "overview": {"type": "string", "description": "2-4 sentence plain-language summary of the day's mail."},
                    "action_items": {
                        "type": "array",
                        "description": "Things the user must do (reply, pay, submit, confirm...). Empty if none.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "task": {"type": "string"},
                                "due": {"type": "string", "description": "e.g. 'Fri 28 Nov' or 'No deadline'"},
                                "email_id": {"type": "string"},
                            },
                            "required": ["task", "due"],
                        },
                    },
                    "calendar_items": {
                        "type": "array",
                        "description": "Dated items found, whether or not they were added to the calendar.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "when": {"type": "string"},
                                "what": {"type": "string"},
                                "added_to_calendar": {"type": "boolean"},
                            },
                            "required": ["when", "what", "added_to_calendar"],
                        },
                    },
                    "emails": {
                        "type": "array",
                        "description": "One entry per email from search_emails.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "from": {"type": "string", "description": "Sender name only, e.g. 'HDFC Bank'."},
                                "category": {"type": "string", "enum": REPORT_CATEGORIES},
                                "summary": {"type": "string", "description": "One short sentence."},
                            },
                            "required": ["id", "from", "category", "summary"],
                        },
                    },
                },
                "required": ["headline", "overview", "action_items", "calendar_items", "emails"],
            },
        },
    },
]

ADDED_TAG = ' <i style="color:#15803d">(added to calendar)</i>'

CATEGORY_COLORS = {  # Google Calendar colorId
    "exam": "11", "deadline": "6", "reschedule": "5", "cancellation": "8",
    "class": "9", "meeting": "7", "travel": "2", "event": "10", "other": "1",
}


class ToolBox:
    def __init__(self, backend) -> None:
        self.backend = backend
        self.tz = ZoneInfo(config.TIMEZONE)
        self.log: list[str] = []
        self.calendar_items = 0  # events created (or found already on calendar) this run
        self.found_ids: list[str] = []  # emails returned by search_emails this run

    # 1
    def search_emails(self, extra_query: str = "") -> dict:
        since = int((datetime.now(self.tz) - timedelta(hours=config.LOOKBACK_HOURS)).timestamp())
        query = f'after:{since} -in:sent -in:chats -in:drafts -subject:"Morning Bell"'
        if config.MAIL_QUERY:
            query += f" {config.MAIL_QUERY}"
        if extra_query:
            query += f" ({extra_query})"
        emails = self.backend.search_emails(query, config.MAX_EMAILS)
        for e in emails:
            if e["id"] not in self.found_ids:
                self.found_ids.append(e["id"])
        return {"count": len(emails), "limit": config.MAX_EMAILS, "emails": emails}

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
            reminder_minutes = [1440, 60] if category in ("exam", "deadline", "travel") else [30]
        reminders = [{"method": "popup", "minutes": int(m)} for m in reminder_minutes[:4]]
        if category in ("exam", "deadline"):
            reminders.append({"method": "email", "minutes": 1440})

        prefix = {"cancellation": "[CANCELLED] ", "reschedule": "[RESCHEDULED] "}.get(category, "")
        for word in ("(Cancelled)", "(Rescheduled)", "Cancelled", "Rescheduled"):
            if prefix and title.lower().endswith(word.lower()):
                title = title[: -len(word)].rstrip(" -–(")
        description = details
        if source_email_id:
            description += f"\n\nFrom email (Gmail id {source_email_id}). Added by Morning Bell."
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
    def send_daily_report(
        self, headline: str, overview: str, emails: list[dict],
        action_items: list[dict] | None = None, calendar_items: list[dict] | None = None,
    ) -> dict:
        action_items = action_items or []
        calendar_items = calendar_items or []
        claimed = sum(1 for i in calendar_items if i.get("added_to_calendar"))
        if claimed > self.calendar_items:
            return {
                "error": f"{claimed} items are marked added_to_calendar, but only {self.calendar_items} events "
                         "were created with create_calendar_event. Create them first, then send the report."
            }
        covered = {e.get("id") for e in emails}
        missing = [i for i in self.found_ids if i not in covered]
        if missing and len(missing) > max(1, len(self.found_ids) // 10):
            return {
                "error": f"The report is missing {len(missing)} of the {len(self.found_ids)} emails. Add one entry "
                         f"for each of these ids, then call send_daily_report again: {missing[:40]}"
            }

        esc = lambda t: _html.escape(str(t or ""))  # noqa: E731
        groups: dict[str, list[dict]] = {}
        for e in emails:
            cat = e.get("category") if e.get("category") in CATEGORY_TITLES else "other"
            groups.setdefault(cat, []).append(e)

        parts = [
            "<div style='font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#222;max-width:680px'>",
            f"<p style='font-size:17px;margin:0 0 6px'><b>🔔 {esc(headline)}</b></p>",
            f"<p style='margin:0 0 16px;color:#444'>{esc(overview)}</p>",
        ]
        if action_items:
            parts.append("<h3 style='margin:16px 0 6px'>✅ Action needed</h3><ul style='margin:0'>")
            parts += [f"<li><b>{esc(a.get('task'))}</b> — <span style='color:#b45309'>{esc(a.get('due'))}</span></li>"
                      for a in action_items]
            parts.append("</ul>")
        if calendar_items:
            parts.append("<h3 style='margin:16px 0 6px'>📅 Dates & events</h3><ul style='margin:0'>")
            parts += [f"<li>{esc(c.get('when'))} — {esc(c.get('what'))}"
                      f"{ADDED_TAG if c.get('added_to_calendar') else ''}</li>"
                      for c in calendar_items]
            parts.append("</ul>")
        parts.append(f"<h3 style='margin:20px 0 6px'>📬 All emails ({len(emails)})</h3>")
        for cat in REPORT_CATEGORIES:
            if cat not in groups:
                continue
            parts.append(f"<p style='margin:12px 0 4px'><b>{CATEGORY_TITLES[cat]}</b> "
                         f"<span style='color:#888'>({len(groups[cat])})</span></p><ul style='margin:0'>")
            parts += [f"<li><b>{esc(e.get('from'))}</b>: {esc(e.get('summary'))}</li>" for e in groups[cat]]
            parts.append("</ul>")
        if not emails:
            parts.append("<p>No new emails in the last 24 hours. 🎉</p>")
        parts.append("<p style='color:#888;font-size:12px;margin-top:20px'>Sent by Morning Bell</p></div>")

        today = datetime.now(self.tz).strftime("%A, %d %B")
        result = self.backend.send_email(f"🔔 Morning Bell — Daily mail report, {today}", "".join(parts))
        self.log.append(f"Report sent: {headline}")
        return {"status": "sent", **result}

    # ---------- helpers ----------
    def _parse(self, value: str) -> datetime:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return dt.replace(tzinfo=self.tz) if dt.tzinfo is None else dt.astimezone(self.tz)

    def call(self, name: str, args: dict):
        fn = {
            "search_emails": self.search_emails,
            "read_email": self.read_email,
            "create_calendar_event": self.create_calendar_event,
            "send_daily_report": self.send_daily_report,
        }.get(name)
        if fn is None:
            raise ValueError(f"Unknown tool {name}")
        return fn(**args)
