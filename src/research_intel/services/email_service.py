from __future__ import annotations

import smtplib
from email.message import EmailMessage

import httpx

from research_intel.config import Settings


class NewsletterEmailService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send(self, *, to: str | None, subject: str, body: str) -> dict:
        provider = (self.settings.email_provider or "resend").lower()
        if not to:
            return {
                "sent": False,
                "provider": provider,
                "message": "Email not sent because no recipient email was provided.",
            }
        if provider == "smtp":
            return await self._send_smtp(to=to, subject=subject, body=body)
        return await self._send_resend(to=to, subject=subject, body=body)

    async def _send_resend(self, *, to: str, subject: str, body: str) -> dict:
        if not self.settings.resend_api_key:
            return {
                "sent": False,
                "provider": "resend",
                "message": "Email not sent because RESEND_API_KEY is not configured.",
            }
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {self.settings.resend_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": self.settings.daily_email_from or self.settings.email_from,
                        "to": [to],
                        "subject": subject,
                        "text": body,
                    },
                )
            if response.status_code < 300:
                return {"sent": True, "provider": "resend", "message": f"Email sent to {to}."}
            return {
                "sent": False,
                "provider": "resend",
                "message": f"Email not sent. Resend returned HTTP {response.status_code}: {response.text[:300]}",
            }
        except Exception as exc:
            return {"sent": False, "provider": "resend", "message": f"Email not sent. {exc}"}

    async def _send_smtp(self, *, to: str, subject: str, body: str) -> dict:
        if not self.settings.smtp_host:
            return {
                "sent": False,
                "provider": "smtp",
                "message": "Email not sent because SMTP_HOST is not configured.",
            }
        try:
            message = EmailMessage()
            message["From"] = self.settings.smtp_from or self.settings.daily_email_from
            message["To"] = to
            message["Subject"] = subject
            message.set_content(body)
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=20) as server:
                server.starttls()
                if self.settings.smtp_username and self.settings.smtp_password:
                    server.login(self.settings.smtp_username, self.settings.smtp_password)
                server.send_message(message)
            return {"sent": True, "provider": "smtp", "message": f"Email sent to {to}."}
        except Exception as exc:
            return {"sent": False, "provider": "smtp", "message": f"Email not sent. {exc}"}
