"""SMTP integration test against Mailpit; no external email account is used."""
import json
import os
import time
from urllib.request import urlopen

import pytest


@pytest.mark.integration
def test_book_notification_is_accepted_by_local_smtp_sink():
    smtp_host = os.getenv("SMTP_HOST", "")
    api_url = os.getenv("MAILPIT_API_URL", "")
    if not smtp_host or smtp_host == "smtp.gmail.com" or not api_url:
        pytest.skip("configure SMTP_HOST and MAILPIT_API_URL to enable SMTP integration test")

    from books_scraper_full import send_email

    def read_messages():
        with urlopen(f"{api_url.rstrip('/')}/api/v1/messages", timeout=3) as response:
            return json.loads(response.read().decode("utf-8")).get("messages", [])

    existing_ids = {message.get("ID") for message in read_messages()}
    recipient = os.getenv("RECEIVER_EMAIL", "test-recipient@example.com")
    send_email(
        [{
            "title": "Integration Test Book",
            "publisher": "Test Publisher",
            "author": "Test Author",
            "price": "0",
            "link": "https://example.test/book",
        }],
        recipient_email=recipient,
    )

    deadline = time.monotonic() + 10
    received = []
    while time.monotonic() < deadline:
        received = [
            message for message in read_messages()
            if message.get("ID") not in existing_ids
            and message.get("Subject") == "📚 Latest Books from Publishers"
        ]
        if received:
            break
        time.sleep(0.25)

    assert received, "Mailpit did not receive the notification message"
    assert any(
        recipient.lower() in json.dumps(message.get("To", [])).lower()
        for message in received
    ), f"notification was not addressed to {recipient}"
