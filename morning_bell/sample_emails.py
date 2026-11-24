"""Realistic sample college emails for demo mode. Dates are relative to today."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import config


def build() -> list[dict]:
    now = datetime.now(ZoneInfo(config.TIMEZONE))
    d = lambda n: (now + timedelta(days=n)).strftime("%A, %d %B %Y")  # noqa: E731
    sent = now.strftime("%a, %d %b %Y %H:%M")
    return [
        {
            "id": "demo-001", "from": "Exam Cell <examcell@college.edu>", "date": sent,
            "subject": "Mid-Semester Examination Schedule - CSE 3rd Year",
            "body": f"Dear Students,\n\nThe mid-semester examinations for CSE 3rd year will be held as follows:\n"
                    f"- Database Management Systems: {d(3)}, 10:00 AM - 12:00 PM, Hall A-201\n"
                    f"- Operating Systems: {d(5)}, 2:00 PM - 4:00 PM, Hall A-202\n\n"
                    "Carry your ID card and hall ticket. Syllabus: Units 1-3.\n\nController of Examinations",
        },
        {
            "id": "demo-002", "from": "Prof. R. Mehta <rmehta@college.edu>", "date": sent,
            "subject": "Computer Networks lecture rescheduled",
            "body": "Hi all,\n\nTomorrow's Computer Networks lecture (usually 11:00-12:00) is moved to 3:00 PM - 4:00 PM "
                    "tomorrow in Room B-104, because of a department meeting.\n\nRegards,\nProf. Mehta",
        },
        {
            "id": "demo-003", "from": "CSE Department <cse-office@college.edu>", "date": sent,
            "subject": "Machine Learning Lab cancelled",
            "body": f"The Machine Learning lab scheduled on {d(2)} from 9:00 AM to 11:00 AM in Lab 3 stands cancelled "
                    "as the lab instructor is on leave. A make-up session will be announced later.",
        },
        {
            "id": "demo-004", "from": "Prof. S. Iyer <siyer@college.edu>", "date": sent,
            "subject": "Software Engineering - Assignment 3 submission",
            "body": f"Reminder: Assignment 3 (UML diagrams for your mini project) must be uploaded to the LMS by "
                    f"11:59 PM on {d(4)}. Late submissions will not be accepted.",
        },
        {
            "id": "demo-005", "from": "Student Activities <activities@college.edu>", "date": sent,
            "subject": "TechFest 2026 - Hackathon registrations open",
            "body": f"Registrations for the 24-hour hackathon are open! The hackathon begins {d(6)} at 9:00 AM in the "
                    "Main Auditorium. Teams of up to 4. Register on the college portal.",
        },
        {
            "id": "demo-006", "from": "Library <library@college.edu>", "date": sent,
            "subject": "New e-journals available",
            "body": "The library has added access to 40 new IEEE e-journals. Log in with your college ID to browse.",
        },
    ]
