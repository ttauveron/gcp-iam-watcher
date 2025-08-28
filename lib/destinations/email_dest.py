import os
import smtplib
from email.message import EmailMessage

from .base import Destination, IamChangeEvent


class EmailDestination(Destination):
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "localhost")
        self.smtp_port = int(os.getenv("SMTP_PORT", "25"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_pass = os.getenv("SMTP_PASS")
        self.from_addr = os.getenv("SMTP_EMAIL_FROM")
        self.to_addr = os.getenv("SMTP_EMAIL_TO")

    def send(self, event: IamChangeEvent) -> None:
        msg = EmailMessage()
        msg["Subject"] = f"[GCP IAM] New Role Grant in {event.resource_display}"
        msg["From"] = self.from_addr
        msg["To"] = self.to_addr

        header = f"New Role Grant in {event.resource_display or 'Unknown'}"
        lines = [
            header,
            f"<b>Asset Type:</b> {event.resource_type}",
            f"<b>Asset Name:</b> {event.resource_name}",
        ]
        for g in event.changes:
            lines.append(f"<b>Role:</b> {g.role}")
            lines.append(f"<b>Granted to:</b> {g.members}")
            if g.condition:
                lines.append(f"<b>With condition:</b> {g.condition}")
        if event.logs_url:
            lines.append(f'<b><a href="{event.logs_url}">Browse Audit Logs</a></b>')

        body = "<br>".join(lines)

        msg.set_content(body)
        msg.add_alternative(body, subtype="html")
        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as s:
            if self.smtp_user and self.smtp_pass:
                s.starttls()
                s.login(self.smtp_user, self.smtp_pass)
            s.send_message(msg)
