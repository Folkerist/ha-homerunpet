"""Request signing of the legacy homerun API (engine/ApiClient.createParam in the app)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .const import APP_SECRET, PWD_KEY, PWD_SALT


def java_str(value: Any) -> str:
    """String.valueOf() as the app applies it to the values of the data map."""
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    return str(value)


def sign(data: dict[str, Any], timestamp: str, secret: str = APP_SECRET) -> str:
    """sha256("k=v&" for keys sorted descending + "appKey=<secret>&timestamp=<ts>")."""
    pairs = "".join(f"{k}={java_str(data[k])}&" for k in sorted(data, reverse=True))
    raw = f"{pairs}appKey={secret}&timestamp={timestamp}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_body(data: dict[str, Any], timestamp: str) -> dict[str, Any]:
    """The envelope every legacy POST carries."""
    return {"data": data, "timestamp": timestamp, "sign": sign(data, timestamp)}


def hash_password(password: str) -> str:
    """common/MD5.MD5Pwd: the password never leaves the phone in clear text."""
    digest = hashlib.md5(f"{PWD_KEY}{password}{PWD_SALT}".encode()).hexdigest()
    return digest[7:27]
