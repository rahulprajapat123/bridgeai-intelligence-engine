from __future__ import annotations

import httpx

from research_intel.config import Settings


class EmailAlertService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send_alert(self, *, to: str, subject: str, body: str) -> bool:
        if self.settings.email_provider != "resend" or not self.settings.resend_api_key:
            return False
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": self.settings.email_from,
                    "to": [to],
                    "subject": subject,
                    "text": body,
                },
            )
            return response.status_code < 300

