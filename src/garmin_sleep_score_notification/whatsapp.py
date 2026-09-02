from __future__ import annotations

import requests


class WhatsAppError(Exception):
    pass


class WhatsAppSender:
    URL = "https://api.callmebot.com/whatsapp.php"

    def send(self, phone: str, apikey: str, message: str) -> None:
        try:
            resp = requests.get(
                self.URL,
                params={"phone": phone, "text": message, "apikey": apikey},
                timeout=30,
            )
        except requests.RequestException as exc:
            raise WhatsAppError(str(exc)) from exc

        body = (resp.text or "").strip()
        if resp.status_code != 200 or not any(
            token in body.lower() for token in ("queued", "sent", "received")
        ):
            raise WhatsAppError(f"HTTP {resp.status_code}: {body[:200]}")
