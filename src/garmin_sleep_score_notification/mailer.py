from __future__ import annotations

import base64

import requests


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
        inline: tuple[str, bytes] | None = None,
    ) -> None:
        if not self.api_key:
            raise EmailError("RESEND_API_KEY is not set")

        body: dict = {
            "from": self.sender,
            "to": to,
            "subject": subject,
            "text": text,
            "html": html,
        }
        if inline is not None:
            cid, content = inline
            body["attachments"] = [
                {
                    "filename": f"{cid}.png",
                    "content": base64.b64encode(content).decode(),
                    "content_id": cid,
                }
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
