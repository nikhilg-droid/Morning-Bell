"""Realistic sample emails (college + personal) for demo mode. Dates are relative to today."""
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
            "tab": "updates",
        },
        {
            "id": "demo-007", "from": "HDFC Bank <alerts@hdfcbank.net>", "date": sent, "important": True,
            "subject": "Credit card statement - payment due",
            "body": f"Your credit card statement is ready. Total amount due: Rs 8,450. Minimum due: Rs 500. "
                    f"Payment due date: {d(5)}. Pay on time to avoid late fees.",
            "tab": "updates",
        },
        {
            "id": "demo-008", "from": "Rahul Sharma <rahul.sharma98@gmail.com>", "date": sent,
            "subject": "Dinner this weekend?",
            "body": f"Hey! A few of us are meeting for dinner at Barbeque Nation, Koramangala on {d(4)} at 8 PM. "
                    "Can you make it? Let me know by tomorrow so I can book the table.",
        },
        {
            "id": "demo-009", "from": "Amazon.in <shipment-tracking@amazon.in>", "date": sent,
            "subject": "Your package will be delivered tomorrow",
            "body": "Your order of boAt Rockerz 450 headphones has shipped and will arrive tomorrow by 9 PM.",
            "tab": "updates",
        },
        {
            "id": "demo-010", "from": "Google <no-reply@accounts.google.com>", "date": sent, "important": True,
            "subject": "Security alert: new sign-in on Windows",
            "body": "Your Google Account was just signed in to from a new Windows device. If this was you, you don't "
                    "need to do anything. If not, we'll help you secure your account.",
        },
        {
            "id": "demo-011", "from": "Swiggy <offers@swiggy.in>", "date": sent,
            "subject": "Flat 60% off on your next 3 orders!",
            "body": "Use code HUNGRY60 to get 60% off. Offer valid till Sunday midnight. Order now!",
            "tab": "promotions",
        },
        {
            "id": "demo-012", "from": "LinkedIn <jobs-noreply@linkedin.com>", "date": sent,
            "subject": "10 new jobs for 'Data Analyst Intern'",
            "body": "New jobs matching your preferences: Data Analyst Intern at Flipkart, Zomato, Razorpay and 7 more.",
            "tab": "social",
        },
    ]
