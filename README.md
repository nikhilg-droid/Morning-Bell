# 🔔 Morning Bell

**An agentic AI assistant that turns your Gmail into a daily report, schedule updates and calendar alerts.**

Every morning Morning Bell reads **all your Gmail from the last 24 hours**, emails you a categorized
report (summary, action items, dates, and a one-line summary of every email grouped as Important, College/Work,
Personal, Finance, Orders, Travel, Security, Social, Newsletters, Promotions), and adds dated items such as
exams, meetings, bill due dates, bookings and invitations to **Google Calendar** with alerts. The reasoning
runs on **Sarvam AI** (`sarvam-105b`) with tool calling.

## How the agent works

```
            ┌──────────────── Sarvam AI (sarvam-105b) decides what to do next ────────────────┐
            │                                                                                 │
 Gmail ──▶ ① search_emails ──▶ ② read_email ──▶ ③ create_calendar_event ──▶ ④ send_daily_report
            (all mail, last 24 h)  (full text of     (Google Calendar event      (categorized report
                                    relevant ones)    + popup/email alerts)       to your Gmail)
```

| # | Tool | What it does | Google API |
|---|------|--------------|------------|
| 1 | `search_emails` | Lists every email from the last 24 h with sender, subject, Gmail tab, important/unread flags and a snippet (spam, trash, sent and chats excluded) | Gmail `messages.list` |
| 2 | `read_email` | Gets the full body of emails whose snippet isn't enough (personal, bills, bookings, deadlines). Promotions and newsletters are not opened. Labels it `MorningBell/Processed` | Gmail `messages.get` / `modify` |
| 3 | `create_calendar_event` | Adds a colour-coded event with reminders (exams/deadlines/travel: 1 day + 1 hour + email; others: 30 min). Skips duplicates and past items | Calendar `events.insert` |
| 4 | `send_daily_report` | Sends one HTML report: headline, overview, ✅ action items, 📅 dates, and every email summarized by category | Gmail `messages.send` |

The agent loop (`morning_bell/agent.py`) sends the conversation and tool list to Sarvam; the model
picks tools, the code runs them and returns the results, and this repeats until the digest is sent.
Guards: the report tool refuses to send if it leaves out emails, or claims events were added that
`create_calendar_event` didn't really create, tool errors are passed back to the model so it can recover, and runs are capped at 25 steps.

## Project layout

```
morning_bell/
  __main__.py       CLI entry:  python -m morning_bell [--demo]
  agent.py          Sarvam AI client + agent loop + system prompt
  tools.py          the 4 tools (schemas + code)
  google_backend.py Gmail/Calendar access (real) and DemoBackend (offline)
  sample_emails.py  sample emails for --demo
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
By default the report covers every email from the last 24 hours. To leave some out, set `MAIL_QUERY`
to a Gmail search, e.g. `MAIL_QUERY=-category:promotions`.

## 2. Try it without Google (demo mode)

```bash
python -m morning_bell --demo
```

Uses 12 sample emails (college notices, a bank bill, a dinner invite, a delivery, a security alert,
promotions), prints the calendar it would create, and writes the report to `demo_digest.html`.

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
Check Google Calendar for the new events and your inbox for "🔔 Morning Bell — Daily mail report, <date>".

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
| `MAIL_QUERY` | (empty = all mail) | Extra Gmail search to narrow the report |
| `MAX_EMAILS` | `60` | Max emails per report |
| `LOOKBACK_HOURS` | `24` | How far back to look |
| `TIMEZONE` | `Asia/Kolkata` | Used to resolve "tomorrow 3 PM" etc. |
| `CALENDAR_ID` | `primary` | Which Google Calendar to write to |
| `DIGEST_TO` | your Gmail | Where to send the report |

Never commit `.env`, `credentials.json` or `token.json` (already in `.gitignore`).
