"""Async client of the legacy homerun API (api.homerunsmart.com).

The CS106 has an EZVIZ Wi-Fi module; the app never talks to EZVIZ for control.
It sends signed POSTs to homerun, and /app/v1/devices/control relays them to the
EZVIZ "otap" property/action API.
"""

from __future__ import annotations

import json
import logging
import secrets
import string
import time
from datetime import date, datetime
from typing import Any

import aiohttp

from .const import (
    APP_ID,
    APP_VERSION,
    APPLICATION_ID,
    BASE_URL_CN,
    CLEAN_DELAY_RANGE,
    CATEG_LITTER_BOX,
    CATEGORY_GLOBAL,
    CODE_AUTH_INVALID,
    CODE_OK,
    DOMAIN_CUSTOM,
    OTAP_ACTION,
    OTAP_PROP,
)
from .exceptions import HomerunApiError, HomerunAuthError, HomerunConnectionError
from .models import AutoClean, Device, NightMode, ToiletVisit, parse_dt
from .signing import build_body, hash_password

_LOGGER = logging.getLogger(__name__)
TIMEOUT = aiohttp.ClientTimeout(total=20)


def _client_device_id() -> str:
    """Same shape as the app's generateUniqueId(): 8 random chars + unix seconds."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8)) + str(int(time.time()))


class HomerunClient:
    """One account. Reuses a token taken from the app; logging in is opt-in (see login())."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        token: str | None = None,
        *,
        base_url: str = BASE_URL_CN,
        lang: str = "RU",
        time_zone: str = "Europe/Moscow",
        client_device_id: str | None = None,
    ) -> None:
        self._session = session
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._lang = lang
        self._time_zone = time_zone
        self._client_device_id = client_device_id or _client_device_id()

    @property
    def token(self) -> str | None:
        return self._token

    def _headers(self, ts: str) -> dict[str, str]:
        headers = {
            "x-lang": self._lang,
            "Accept-Language": self._lang,
            "Content-Type": "application/json",
            "X-Application-Id": APPLICATION_ID,
            "X-Client-Platform": "Android",
            "X-Client-App-Version": APP_VERSION,
            "X-Client-Device-Id": self._client_device_id,
            "X-Client-Time-Zone": self._time_zone,
            "X-Sign-Timestamp": ts,
        }
        if self._token:
            headers["x-token"] = self._token
        return headers

    async def request(self, path: str, data: dict[str, Any] | None = None) -> Any:
        """POST a signed request, return its `data`. Never logs the token or the body."""
        ts = str(int(time.time()))
        body = build_body(data or {}, ts)
        try:
            async with self._session.post(
                self._base_url + path,
                data=json.dumps(body, separators=(",", ":"), ensure_ascii=False),
                headers=self._headers(ts),
                timeout=TIMEOUT,
            ) as resp:
                if resp.status >= 400:
                    raise HomerunConnectionError(f"{path}: HTTP {resp.status}")
                payload = await resp.json(content_type=None)
        except (TimeoutError, aiohttp.ClientError, ValueError) as err:
            raise HomerunConnectionError(f"{path}: {type(err).__name__}") from err
        if not isinstance(payload, dict):
            raise HomerunConnectionError(f"{path}: unexpected answer")
        code = str(payload.get("code"))
        if code == CODE_AUTH_INVALID:
            raise HomerunAuthError(payload.get("msg") or "token rejected")
        if code != CODE_OK:
            raise HomerunApiError(code, str(payload.get("msg") or ""), path)
        _LOGGER.debug("%s ok", path)
        return payload.get("data")

    # --- Auth -------------------------------------------------------------------------

    async def login_password(
        self, *, phone: str, password: str, area_code: str = "86", country_code: str = "CN"
    ) -> str:
        """Fresh login. WARNING: may end the app's session on the phone (code 4001 there).

        Only call it when the user opted in (allow_password_login).
        """
        data = {
            "countryCode": country_code,
            "region": country_code,
            "langType": self._lang,
            "appId": APP_ID,
            "areaCode": area_code,
            "phone": phone,
            "password": hash_password(password),
            "deviceId": self._client_device_id,
            "model": "HomeAssistant",
        }
        result = await self.request("/app/v1/login/phonePassword", data)
        token = (result or {}).get("token")
        if not token:
            raise HomerunAuthError("login returned no token")
        self._token = token
        return token

    # --- Account and devices ------------------------------------------------------------

    async def families(self) -> list[dict[str, Any]]:
        data = await self.request("/app/v1/family/list", {})
        return list((data or {}).get("list") or [])

    async def devices(self, family_id: int) -> list[Device]:
        data = await self.request(
            "/app/v1/devices/list", {"familyId": family_id, "page": 1, "limit": 100}
        )
        return [Device.from_api(d) for d in (data or {}).get("list") or [] if d.get("deviceSerial")]

    async def litter_boxes(self, families: list[dict[str, Any]] | None = None) -> list[Device]:
        """All litter boxes of every family of the account."""
        found: dict[str, Device] = {}
        if families is None:
            families = await self.families()
        for family in families:
            if family.get("id") is None:
                continue
            for dev in await self.devices(family["id"]):
                if dev.categ == CATEG_LITTER_BOX:
                    found.setdefault(dev.serial, dev)
        return list(found.values())

    async def device_status(self, serial: str) -> int:
        data = await self.request("/app/v1/devices/status", {"deviceSerial": serial})
        return int((data or {}).get("status") or 0)

    async def version_info(self, serial: str) -> dict[str, Any]:
        return await self.request("/app/v1/devices/versionInfo", {"deviceSerial": serial}) or {}

    async def toilet_visits(self, serial: str, day: date) -> list[ToiletVisit]:
        data = await self.request(
            "/app/v1/devicesToiletData/list", {"deviceSerial": serial, "doDate": day.isoformat()}
        )
        visits = [ToiletVisit.from_api(r) for r in (data or {}).get("list") or []]
        return sorted((v for v in visits if v), key=lambda v: v.time)

    async def cleanings(self, serial: str, day: date) -> list[datetime]:
        data = await self.request(
            "/app/v1/devicesCleanData/list", {"deviceSerial": serial, "doDate": day.isoformat()}
        )
        times = [parse_dt(r.get("dateTime")) for r in (data or {}).get("list") or []]
        return sorted(t for t in times if t)

    async def faults(self, serial: str) -> list[str]:
        """Active exceptions (`detailsTopKey` are localisation keys of the app)."""
        data = await self.request("/app/v1/devicesExceptionStatus/list", {"deviceSerial": serial})
        out = []
        for item in (data or {}).get("list") or []:
            key = item.get("detailsTopKey") or item.get("detailsTopDes")
            if key:
                out.append(str(key))
        return out

    # --- EZVIZ otap proxy ---------------------------------------------------------------

    async def _otap(
        self,
        serial: str,
        *,
        url: str,
        method: str,
        identifier_key: str,
        identifier: str,
        body: str,
        category: str,
        domain: str,
    ) -> Any:
        headers = {
            "Content-Type": "application/json",
            "deviceSerial": serial,
            "localIndex": 0,
            "resourceCategory": category,
            "domainIdentifier": domain,
            identifier_key: identifier,
        }
        data = {
            "url": url,
            "method": method,
            "headers": json.dumps(headers, separators=(",", ":")),
            "body": body,
        }
        result = await self.request("/app/v1/devices/control", data)
        if result is None:
            result = {}
        if not isinstance(result, dict):
            raise HomerunApiError("?", "unexpected otap answer", f"otap {identifier}")
        meta = result.get("meta") or {}
        meta_code = str(meta.get("code", CODE_OK))
        if meta_code != CODE_OK:
            raise HomerunApiError(meta_code, str(meta.get("message") or ""), f"otap {identifier}")
        return result.get("data")

    async def get_prop(
        self, serial: str, name: str, *, category: str = CATEGORY_GLOBAL, domain: str = DOMAIN_CUSTOM
    ) -> Any:
        return await self._otap(
            serial, url=OTAP_PROP, method="GET", identifier_key="propIdentifier",
            identifier=name, body="{}", category=category, domain=domain,
        )

    async def set_prop(
        self,
        serial: str,
        name: str,
        value: Any,
        *,
        category: str = CATEGORY_GLOBAL,
        domain: str = DOMAIN_CUSTOM,
    ) -> Any:
        return await self._otap(
            serial, url=OTAP_PROP, method="PUT", identifier_key="propIdentifier",
            identifier=name, body=json.dumps(value, separators=(",", ":")),
            category=category, domain=domain,
        )

    async def action(
        self,
        serial: str,
        name: str,
        body: str,
        *,
        category: str = CATEGORY_GLOBAL,
        domain: str = DOMAIN_CUSTOM,
    ) -> Any:
        """Invoke an action. `body` goes on the wire as is, the way the app builds it:
        a JSON object string for some actions, a bare value like `1` for others.
        """
        return await self._otap(
            serial, url=OTAP_ACTION, method="PUT", identifier_key="actionIdentifier",
            identifier=name, body=body, category=category, domain=domain,
        )

    # --- Litter box commands ------------------------------------------------------------

    async def clean_now(self, serial: str) -> None:
        # DeviceCatLitterBoxFragment.SetManualShovel: JSONObject({"value": null})
        await self.action(serial, "ManualShovel", '{"value":null}')

    async def level_litter(self, serial: str) -> None:
        """Not on the CS106 (code 4000); the app hides it for EZVIZ boxes."""
        await self.action(serial, "ManualLayingCatLitter", "1")

    async def refill_litter(self, serial: str, portions: int = 1) -> None:
        if not 1 <= portions <= 3:
            raise ValueError("portions must be 1..3")
        await self.action(serial, "AutomaticSand", str(portions))

    # --- Composite settings: read-modify-write ------------------------------------------

    async def update_auto_clean(
        self, serial: str, *, enabled: bool | None = None, delay_min: int | None = None
    ) -> AutoClean:
        """Change one field of AutoShovel, keeping the other as the box has it now."""
        if delay_min is not None and not CLEAN_DELAY_RANGE[0] <= delay_min <= CLEAN_DELAY_RANGE[1]:
            raise ValueError(f"delay must be {CLEAN_DELAY_RANGE[0]}..{CLEAN_DELAY_RANGE[1]} min")
        current = AutoClean.from_api(await self.get_prop(serial, "AutoShovel"))
        if current is None:
            raise HomerunApiError("?", "cannot read current AutoShovel", "otap AutoShovel")
        new = AutoClean(
            enabled=current.enabled if enabled is None else enabled,
            delay_min=current.delay_min if delay_min is None else delay_min,
        )
        await self.set_prop(serial, "AutoShovel", new.to_api())
        return new

    async def update_night_mode(self, serial: str, *, enabled: bool) -> NightMode:
        """Switch night mode, keeping the window as the box has it now."""
        current = NightMode.from_api(await self.get_prop(serial, "NightMode"))
        if current is None:
            raise HomerunApiError("?", "cannot read current NightMode", "otap NightMode")
        new = NightMode(enabled=enabled, start_s=current.start_s, end_s=current.end_s)
        await self.set_prop(serial, "NightMode", new.to_api())
        return new
