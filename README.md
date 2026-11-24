# 🔔 Morning Bell

**An agentic AI assistant that turns college email into schedule updates and calendar alerts.**

Every morning Morning Bell reads your new college emails in **Gmail**, finds the classes, reschedules,
cancellations, exams, deadlines and events, puts them on **Google Calendar** with alerts, and emails you a
one-page morning digest. The reasoning runs on **Sarvam AI** (`sarvam-105b`) with tool calling.

## How the agent works

```
            ┌──────────────── Sarvam AI (sarvam-105b) decides what to do next ────────────────┐
            │                                                                                 │
 Gmail ──▶ ① search_college_emails ──▶ ② read_email ──▶ ③ create_calendar_event ──▶ ④ send_morning_digest
            (find new college mail)    (full text of     (Google Calendar event      (summary email to
                                        relevant ones)    + popup/email alerts)       your Gmail)
```

| # | Tool | What it does | Google API |
|---|------|--------------|------------|
| 1 | `search_college_emails` | Lists unprocessed college emails from the last 24 h (your `COLLEGE_QUERY`) | Gmail `messages.list` |
| 2 | `read_email` | Gets the full body of one email and labels it `MorningBell/Processed` so it isn't read twice | Gmail `messages.get` / `modify` |
| 3 | `create_calendar_event` | Adds a colour-coded event with reminders (exams/deadlines: 1 day + 1 hour + email; classes: 30 min). Skips duplicates and past items | Calendar `events.insert` |
| 4 | `send_morning_digest` | Sends one HTML summary email ("2 exams this week, 1 class cancelled…") | Gmail `messages.send` |

The agent loop (`morning_bell/agent.py`) sends the conversation and tool list to Sarvam; the model
picks tools, the code runs them and returns the results, and this repeats until the digest is sent.
Guards: the digest tool refuses to report events as added unless `create_calendar_event` really created
them, tool errors are passed back to the model so it can recover, and runs are capped at 25 steps.

## Project layout

```
morning_bell/
  __main__.py       CLI entry:  python -m morning_bell [--demo]
  agent.py          Sarvam AI client + agent loop + system prompt
  tools.py          the 4 tools (schemas + code)
  google_backend.py Gmail/Calendar access (real) and DemoBackend (offline)
  sample_emails.py  sample college emails for --demo
  config.py         settings from .env
```

## 1. Install

```bash
python -m venv .venv
```
```bash
source .venv/bin/activate      # Windows: .venv\Scripts\activate
```
On Windows, use `py` (or `python`) for the commands below; it may print warnings about Scripts not
on PATH, which are safe to ignore.
```bash
pip install -r requirements.txt
```
```bash
cp .env.example .env           # Windows Command Prompt: copy .env.example .env
```
Then open `.env` in a text editor (Windows: `notepad .env`).

Put your Sarvam key in `.env` (`SARVAM_API_KEY=...`, from https://dashboard.sarvam.ai).
`COLLEGE_QUERY` is a normal Gmail search. The default finds any email that mentions exams, classes,
labs, deadlines and so on, so you don't need a college email domain. You can narrow it later, e.g.
`from:(teacher@gmail.com)` or `label:college`.

## 2. Try it without Google (demo mode)

```bash
python -m morning_bell --demo
```

Uses 6 sample college emails (exam schedule, reschedule, lab cancellation, assignment deadline,
hackathon, library newsletter), prints the calendar it would create, and writes the digest to
`demo_digest.html`.

## 3. Google setup (one time, free)

1. Go to https://console.cloud.google.com → create a project (e.g. "Morning Bell").
2. **APIs & Services → Library** → enable **Gmail API** and **Google Calendar API**.
3. **APIs & Services → OAuth consent screen** → External → fill the app name and your email →
   under **Test users** add your Gmail address.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID** → type **Desktop app** →
   download the JSON and save it as `credentials.json` in this folder.

## 4. Run for real

```bash
python -m morning_bell
```

The first run opens a browser to sign in to Google; after that `token.json` is reused.
Check Google Calendar for the new events and your inbox for "🔔 Morning Bell — <date>".

## 5. Run it every morning

**Linux / macOS (cron, 7:00 AM daily):**
```bash
crontab -e
```
then add (change the path):
```
0 7 * * * cd /path/to/morning-bell && .venv/bin/python -m morning_bell --quiet >> morning_bell.log 2>&1
```

**Windows:** Task Scheduler → Create Basic Task → Daily 7:00 AM → Program
`C:\path\to\morning-bell\.venv\Scripts\python.exe`, arguments `-m morning_bell --quiet`,
start in `C:\path\to\morning-bell`.

## Settings (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `SARVAM_API_KEY` | – | Sarvam AI key (required) |
| `SARVAM_MODEL` | `sarvam-105b` | Sarvam chat model |
| `COLLEGE_QUERY` | schedule keywords | Gmail search for which emails to check |
| `LOOKBACK_HOURS` | `24` | How far back to look |
| `TIMEZONE` | `Asia/Kolkata` | Used to resolve "tomorrow 3 PM" etc. |
| `CALENDAR_ID` | `primary` | Which Google Calendar to write to |
| `DIGEST_TO` | your Gmail | Where to send the digest |

Never commit `.env`, `credentials.json` or `token.json` (already in `.gitignore`).
