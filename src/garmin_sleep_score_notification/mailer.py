from __future__ import annotations

import base64
from collections.abc import Sequence

import requests

from .email_content import Attachment


class EmailError(Exception):
    pass


class EmailSender:
    URL = "https://api.resend.com/emails"

    def __init__(self, api_key: str, sender: str) -> None:
        self.api_key = api_key
        self.sender = sender

    def send(
        self,
        to: str,
        subject: str,
        text: str,
        html: str,
        attachments: Sequence[Attachment] = (),
    ) -> None:
        if not self.api_key:
            raise EmailError("RESEND_API_KEY is not set")
        body = {
            "from": self.sender,
            "to": to,
            "subject": subject,
            "text": text,
            "html": html,
        }
        if attachments:
            body["attachments"] = [
                {
                    "filename": a.filename,
                    "content": base64.b64encode(a.content).decode("ascii"),
                    "content_id": a.content_id,
                }
                for a in attachments
            ]
        try:
            resp = requests.post(
                self.URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
                timeout=30,
            )
        except requests.RequestException as exc:
            raise EmailError(str(exc)) from exc

        if resp.status_code != 200:
            raise EmailError(f"HTTP {resp.status_code}: {resp.text[:200]}")
