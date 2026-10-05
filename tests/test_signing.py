"""Signature of the legacy API.

The algorithm was checked against 20 signatures the app produced in a live session
(not committed: they contain the device serial) and the server accepts it.
"""

from __future__ import annotations

import hashlib

from api.const import APP_SECRET
from api.signing import build_body, hash_password, java_str, sign


def test_sign_sorts_keys_descending_and_appends_secret():
    data = {"deviceSerial": "C5F40390:TEST00001", "page": 1, "limit": 100}
    raw = f"page=1&limit=100&deviceSerial=C5F40390:TEST00001&appKey={APP_SECRET}&timestamp=1791208218"
    assert sign(data, "1791208218") == hashlib.sha256(raw.encode()).hexdigest()


def test_sign_empty_data():
    raw = f"appKey={APP_SECRET}&timestamp=1"
    assert sign({}, "1") == hashlib.sha256(raw.encode()).hexdigest()


def test_java_str_matches_string_value_of():
    assert java_str(True) == "true"
    assert java_str(False) == "false"
    assert java_str(None) == "null"
    assert java_str(5) == "5"
    assert java_str({"a": 1}) == '{"a":1}'


def test_build_body_envelope():
    body = build_body({"x": "y"}, "42")
    assert body["data"] == {"x": "y"}
    assert body["timestamp"] == "42"
    assert body["sign"] == sign({"x": "y"}, "42")


def test_password_hash_is_20_hex_chars_and_stable():
    h = hash_password("secret")
    assert len(h) == 20
    assert h == hash_password("secret")
    assert all(c in "0123456789abcdef" for c in h)
