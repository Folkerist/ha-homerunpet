"""Errors raised by the homerun client."""

from __future__ import annotations


class HomerunError(Exception):
    """Base error."""


class HomerunConnectionError(HomerunError):
    """Network failure or a non-JSON / non-2xx answer."""


class HomerunAuthError(HomerunError):
    """Code 4001: the token is no longer valid (expired, or the account logged in elsewhere)."""


class HomerunApiError(HomerunError):
    """Any other non-200 business code, from homerun or the EZVIZ proxy behind it."""

    def __init__(self, code: str, msg: str, path: str) -> None:
        super().__init__(f"{path}: code {code}: {msg}")
        self.code = code
        self.msg = msg
        self.path = path
