import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from braevity.core.models import Job

logger = logging.getLogger(__name__)


def build_email_body(jobs: list[Job], role: str) -> str:
    rows = ""
    for j in jobs:
        rows += (
            f"<tr><td>{j.title}</td><td>{j.company}</td>"
            f"<td>{j.location or ''}</td><td>{j.posted_date or ''}</td>"
            f'<td><a href="{j.url}">Apply</a></td></tr>\n'
        )
    return (
        f"<h2>Braevity: {len(jobs)} new {role} postings</h2>"
        f"<table border='1' cellpadding='5' cellspacing='0'>"
        f"<tr><th>Title</th><th>Company</th><th>Location</th>"
        f"<th>Posted</th><th>Link</th></tr>\n{rows}</table>"
    )


def send_notification(jobs: list[Job], role: str, config: dict) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Braevity: {len(jobs)} new {role} postings found"
        msg["From"] = config["smtp_user"]
        msg["To"] = config["email"]

        body = build_email_body(jobs, role)
        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(config["smtp_host"], config["smtp_port"]) as server:
            server.starttls()
            server.login(config["smtp_user"], config["smtp_password"])
            server.send_message(msg)

        logger.info("Email sent to %s: %d jobs", config["email"], len(jobs))
        return True
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        return False
