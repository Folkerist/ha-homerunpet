"""Load the cloud client from the integration without Home Assistant installed."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "custom_components" / "homerun"))

FIXTURES = HERE / "fixtures"
SERIAL = "C5F40390:TEST00001"


def load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def fx():
    return load


class FakeResponse:
    def __init__(self, status: int, payload):
        self.status = status
        self._payload = payload

    async def json(self, content_type=None):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    """Stands in for aiohttp.ClientSession: queued answers per URL, records requests."""

    def __init__(self):
        self.answers: dict[str, list[tuple[int, object]]] = {}
        self.calls: list[tuple[str, dict, dict]] = []

    def add(self, url: str, payload=None, status: int = 200):
        self.answers.setdefault(url, []).append((status, payload))

    def post(self, url, *, data, headers, timeout):
        self.calls.append((url, json.loads(data), headers))
        status, payload = self.answers[url].pop(0)
        return FakeResponse(status, payload)

    def sent(self, url):
        return [(body, headers) for u, body, headers in self.calls if u == url]
