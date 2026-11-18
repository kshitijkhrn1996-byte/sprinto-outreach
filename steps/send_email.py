"""Step 7 - send via Gmail SMTP. Recipient is hardcoded to my own inbox."""
import smtplib
from email.message import EmailMessage

import config


def send_email(draft: dict, poc: dict, company: dict) -> dict:
    if not (config.GMAIL_ADDRESS and config.GMAIL_APP_PASSWORD):
        raise RuntimeError("Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env to send.")
    msg = EmailMessage()
    msg["From"] = f"{config.SENDER_NAME} <{config.GMAIL_ADDRESS}>"
    msg["To"] = config.TO_EMAIL  # hardcoded - never the prospect
    msg["Subject"] = draft["subject"]
    # Note at the bottom so the review copy shows who it was meant for.
    msg.set_content(
        f"{draft['body']}\n\n---\n[Review copy] Intended for: {poc['name']} <{poc['email']}>, "
        f"{poc.get('position')} at {company.get('company_name')}"
    )
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
        smtp.send_message(msg)
    return {"sent": True, "to": config.TO_EMAIL}
