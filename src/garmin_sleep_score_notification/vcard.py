from __future__ import annotations

import base64

_FOLD_LIMIT = 75


def build_vcard(name: str, email: str, photo_png: bytes) -> bytes:
    b64 = base64.b64encode(photo_png).decode("ascii")
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"N:;{name};;;",
        f"FN:{name}",
        f"EMAIL;TYPE=INTERNET:{email}",
        _fold(f"PHOTO;ENCODING=b;TYPE=PNG:{b64}"),
        "END:VCARD",
    ]
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def _fold(line: str) -> str:
    if len(line) <= _FOLD_LIMIT:
        return line
    parts = [line[:_FOLD_LIMIT]]
    rest = line[_FOLD_LIMIT:]
    while rest:
        parts.append(" " + rest[: _FOLD_LIMIT - 1])
        rest = rest[_FOLD_LIMIT - 1 :]
    return "\r\n".join(parts)
