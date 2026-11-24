"""Morning Bell agent loop (Sarvam AI chat-completions with tool calling)."""
from __future__ import annotations

import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from . import config
from .tools import TOOL_SCHEMAS, ToolBox

SYSTEM_PROMPT = """You are Morning Bell, an assistant that turns the user's Gmail into a daily report and calendar alerts.

Today is {today} ({tz}).
Next 14 days (use these exact weekday/date pairs): {upcoming}

Your job, every morning:
1. Call search_emails to list every email from the last 24 hours.
2. Call read_email for emails whose snippet is not enough to summarize them or that may contain a date,
   time, deadline, booking, payment due or request for action (personal, college/work, finance, travel,
   appointments, invitations). Do NOT open promotions, newsletters or social notifications.
3. For each concrete future dated item, call create_calendar_event (meetings, classes, exams, interviews,
   appointments, bill or assignment deadlines, travel, events/invitations). Resolve relative dates
   ("tomorrow", "next Monday") against today's date, in {tz}. If a date has no time, use 09:00-09:30 for
   events and 23:00-23:30 for deadlines. Never add sale or offer expiry dates.
4. Finally call send_daily_report exactly once. In 'emails', give a short one-sentence summary and a
   category for every email that matters (primary tab, personal, college/work, finance, travel, security,
   anything important). You may leave out promotions, social and newsletter emails: they are listed
   automatically. Use "important" only for mail that truly matters today (money, security, deadlines,
   direct personal requests). List anything the user must do in action_items.

Rules: the ONLY way to put something on the calendar is calling create_calendar_event — one call per item,
all BEFORE send_daily_report. Never say an event was added unless that tool returned "created" or
"already on calendar". Never invent dates, times, amounts or places that are not in the emails. Skip items
already in the past. When everything is done, reply with a short plain-text summary for the console."""


class SarvamClient:
    def __init__(self) -> None:
        if not config.SARVAM_API_KEY:
            raise SystemExit("Set SARVAM_API_KEY in your environment or .env file.")
        self.session = requests.Session()
        self.session.headers.update({
            "api-subscription-key": config.SARVAM_API_KEY,
            "Content-Type": "application/json",
        })

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        payload = {
            "model": config.SARVAM_MODEL,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.2,
            "max_tokens": config.MAX_OUTPUT_TOKENS,
        }
        for attempt in range(4):
            resp = self.session.post(f"{config.SARVAM_BASE_URL}/chat/completions", json=payload, timeout=180)
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** attempt * 2)
                continue
            if resp.status_code >= 400:
                raise RuntimeError(f"Sarvam API error {resp.status_code}: {resp.text[:500]}")
            return resp.json()["choices"][0]
        raise RuntimeError("Sarvam API kept failing")


def run(backend, verbose: bool = True) -> str:
    tz = ZoneInfo(config.TIMEZONE)
    now = datetime.now(tz)
    today = now.strftime("%A, %d %B %Y, %H:%M")
    from datetime import timedelta
    upcoming = ", ".join((now + timedelta(days=i)).strftime("%a %d %b") for i in range(1, 15))
    toolbox = ToolBox(backend)
    llm = SarvamClient()

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT.format(today=today, tz=config.TIMEZONE, upcoming=upcoming)},
        {"role": "user", "content": "Good morning! Summarize my email from the last day and update my calendar."},
    ]
    digest_sent = False
    nudges = 0

    def fallback(reason: str) -> str:
        if verbose:
            print(f"  ⚠️  {reason} - sending a basic report instead.")
        try:
            toolbox.send_fallback_report(reason)
            return f"Sent a basic report (AI could not finish: {reason})."
        except Exception as exc:
            return f"Could not send any report: {type(exc).__name__}: {exc}"

    for step in range(config.MAX_AGENT_STEPS):
        try:
            choice = llm.chat(messages, TOOL_SCHEMAS)
        except Exception as exc:
            return fallback(f"Sarvam API problem: {exc}")
        msg = choice["message"]
        tool_calls = msg.get("tool_calls") or []

        if choice.get("finish_reason") == "length":
            # Reply was cut off - any tool call in it is incomplete, so drop it and ask for a shorter one.
            if verbose:
                print("  ✂️  AI reply was too long and got cut off - asking for a shorter one")
            messages.append({"role": "user", "content": (
                "Your last reply was cut off because it was too long, so nothing was done. Try again with a "
                "much shorter reply: one short sentence per email, and leave promotions, social and newsletter "
                "emails out of send_daily_report (they are listed automatically).")})
            continue

        assistant_msg = {"role": "assistant", "content": msg.get("content") or ""}
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        messages.append(assistant_msg)

        if not tool_calls:
            if digest_sent:
                return (msg.get("content") or "").strip() or "Done."
            if nudges >= 2:
                return fallback("the AI stopped before sending the report")
            nudges += 1
            messages.append({"role": "user", "content": "You have not called send_daily_report yet. Please finish the job."})
            continue

        for call in tool_calls:
            name = call["function"]["name"]
            args: dict = {}
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
                if not isinstance(args, dict):
                    raise ValueError("arguments must be a JSON object")
                result = toolbox.call(name, args)
                if name == "send_daily_report" and "error" not in result:
                    digest_sent = True
            except Exception as exc:  # report errors back to the model so it can recover
                result = {"error": f"{type(exc).__name__}: {exc}"}
            if verbose:
                short = json.dumps(args, ensure_ascii=False)[:100]
                status = f"ERROR: {str(result['error'])[:160]}" if "error" in result else "ok"
                print(f"  🔧 {name}({short}) -> {status}")
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(result, ensure_ascii=False, default=str)[:12000],
            })

    if digest_sent:
        return "Done."
    return fallback("reached the maximum number of steps")
