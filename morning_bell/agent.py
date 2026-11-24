"""Morning Bell agent loop (Sarvam AI chat-completions with tool calling)."""
from __future__ import annotations

import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from . import config
from .tools import TOOL_SCHEMAS, ToolBox

SYSTEM_PROMPT = """You are Morning Bell, an assistant that turns a college student's emails into schedule updates.

Today is {today} ({tz}).

Your job, every morning:
1. Call search_college_emails to list new college emails.
2. For every email that could affect the student's schedule (classes, timetable changes, reschedules,
   cancellations, exams, quizzes, labs, viva, assignment/project deadlines, fee or registration deadlines,
   college events), call read_email to get the full text. Skip obvious newsletters/ads.
3. For each concrete dated item, call create_calendar_event. Resolve relative dates ("tomorrow",
   "next Monday") against today's date. Use local time {tz}. If an email gives a date but no time,
   use 09:00-09:30 for events and 23:00-23:30 for deadlines (unless a time is stated). For a cancellation,
   create a short event titled with the cancelled class at its original slot (category "cancellation").
   For a reschedule, create the event at the NEW time (category "reschedule").
4. Finally call send_morning_digest exactly once with every item you found, sorted by date — including
   notices that have no date (added_to_calendar=false).

Rules: the ONLY way to put something on the calendar is calling create_calendar_event — one call per item,
and all of them BEFORE send_morning_digest. Never say an event was added unless that tool returned
"created" or "already on calendar". Never invent dates, times or rooms that are not in the emails. Do not add items that are already
in the past. When everything is done, reply with a short plain-text summary for the console."""


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
    today = datetime.now(tz).strftime("%A, %d %B %Y, %H:%M")
    toolbox = ToolBox(backend)
    llm = SarvamClient()

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT.format(today=today, tz=config.TIMEZONE)},
        {"role": "user", "content": "Good morning! Check my college email and update my schedule."},
    ]
    digest_sent = False

    for step in range(config.MAX_AGENT_STEPS):
        choice = llm.chat(messages, TOOL_SCHEMAS)
        msg = choice["message"]
        tool_calls = msg.get("tool_calls") or []

        assistant_msg = {"role": "assistant", "content": msg.get("content") or ""}
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        messages.append(assistant_msg)

        if not tool_calls:
            if not digest_sent and step < config.MAX_AGENT_STEPS - 1:
                # Nudge once if the model stopped before sending the digest.
                messages.append({"role": "user", "content": "You have not called send_morning_digest yet. Please finish the job."})
                continue
            return (msg.get("content") or "").strip()

        for call in tool_calls:
            name = call["function"]["name"]
            args: dict = {}
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
                if not isinstance(args, dict):
                    raise ValueError("arguments must be a JSON object")
                result = toolbox.call(name, args)
                if name == "send_morning_digest" and "error" not in result:
                    digest_sent = True
            except Exception as exc:  # report errors back to the model so it can recover
                result = {"error": f"{type(exc).__name__}: {exc}"}
            if verbose:
                short = json.dumps(args, ensure_ascii=False)[:120]
                status = "ERROR" if "error" in result else "ok"
                print(f"  🔧 {name}({short}) -> {status}")
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(result, ensure_ascii=False, default=str)[:12000],
            })

    return "Stopped: reached the maximum number of agent steps."
