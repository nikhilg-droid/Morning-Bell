"""Run:  python -m morning_bell          (real Gmail + Google Calendar)
        python -m morning_bell --demo   (sample emails, nothing written to Google)"""
import argparse
import sys
import json

from . import agent


def main() -> None:
    # Windows consoles may not support emoji; never crash on printing.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(prog="morning_bell", description="Turn college email into calendar alerts.")
    parser.add_argument("--demo", action="store_true", help="use sample emails; don't touch Google")
    parser.add_argument("--quiet", action="store_true", help="don't print each tool call")
    args = parser.parse_args()

    if args.demo:
        from .google_backend import DemoBackend
        backend = DemoBackend()
    else:
        from .google_backend import GoogleBackend
        backend = GoogleBackend()

    print("🔔 Morning Bell is checking your college email...\n")
    summary = agent.run(backend, verbose=not args.quiet)
    print("\n" + summary)

    if args.demo:
        print(f"\n📅 Demo calendar ({len(backend.events)} events):")
        for ev in backend.events:
            alerts = [r["minutes"] for r in ev["reminders"]["overrides"]]
            print(f"  • {ev['start']['dateTime'][:16]}  {ev['summary']}  [{ev['location'] or '-'}]  alerts(min before)={alerts}")
        if backend.sent:
            print("\n📧 Digest written to demo_digest.html")


if __name__ == "__main__":
    main()
