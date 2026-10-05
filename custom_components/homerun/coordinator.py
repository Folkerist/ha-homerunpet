"""Polling coordinator: one per account, state of every litter box in it."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    AutoClean,
    Device,
    HomerunAuthError,
    HomerunClient,
    HomerunError,
    LitterBoxState,
    LitterMargin,
    NightMode,
    ToiletVisit,
)
from .api.models import parse_bool
from .const import DOMAIN, SCAN_INTERVAL, SETTINGS_EVERY

_LOGGER = logging.getLogger(__name__)

type HomerunConfigEntry = ConfigEntry[HomerunCoordinator]

# (attribute of LitterBoxState, property name, parser)
SETTINGS: tuple[tuple[str, str, Callable[[Any], Any]], ...] = (
    ("auto_clean", "AutoShovel", AutoClean.from_api),
    ("child_lock", "ChildLock", parse_bool),
    ("kitten_protection", "KittenProtection", parse_bool),
    ("auto_refill", "AutomaticSandAddingSwitch", parse_bool),
    ("auto_burial", "AutomaticBurial", parse_bool),
    ("night_mode", "NightMode", NightMode.from_api),
)


class HomerunCoordinator(DataUpdateCoordinator[dict[str, LitterBoxState]]):
    """Fast part (status, task, containers, visits) every minute, settings every 10 min."""

    config_entry: HomerunConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: HomerunConfigEntry, client: HomerunClient, devices: list[Device]
    ) -> None:
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=SCAN_INTERVAL
        )
        self.client = client
        self.devices = {d.serial: d for d in devices}
        self._settings_at: dict[str, datetime] = {}
        self._day: date | None = None
        # Survive midnight, when the "today" lists become empty.
        self.last_visit: dict[str, ToiletVisit] = {}
        self.last_clean: dict[str, datetime] = {}

    async def _async_update_data(self) -> dict[str, LitterBoxState]:
        now = dt_util.now()
        # First refresh and the first one of a new day also read yesterday: fills the
        # "last" sensors after a restart and catches visits made just before midnight.
        with_yesterday = self._day != now.date()
        result: dict[str, LitterBoxState] = {}
        try:
            for serial in self.devices:
                prev = (self.data or {}).get(serial)
                result[serial] = await self._read_box(serial, prev, now, with_yesterday)
        except HomerunAuthError as err:
            raise ConfigEntryAuthFailed(
                "The homerun token is no longer valid. Take a fresh one from the app."
            ) from err
        except HomerunError as err:
            raise UpdateFailed(str(err)) from err
        self._day = now.date()
        return result

    async def _read_box(
        self, serial: str, prev: LitterBoxState | None, now: datetime, with_yesterday: bool
    ) -> LitterBoxState:
        c = self.client
        state = LitterBoxState()
        if prev is not None:  # settings are kept between slow reads and on read errors
            for attr, _prop, _conv in SETTINGS:
                setattr(state, attr, getattr(prev, attr))
            state.firmware, state.firmware_latest = prev.firmware, prev.firmware_latest

        state.online = await c.device_status(serial) == 1
        today = now.date()
        state.visits_today = await c.toilet_visits(serial, today)
        state.cleans_today = await c.cleanings(serial, today)
        state.recent_visits = list(state.visits_today)
        if with_yesterday:
            yesterday = today - timedelta(days=1)
            old_visits = await c.toilet_visits(serial, yesterday)
            state.recent_visits = old_visits + state.recent_visits
            if old_visits:
                self._remember_visit(serial, old_visits[-1])
            old_cleans = await c.cleanings(serial, yesterday)
            if old_cleans:
                self._remember_clean(serial, old_cleans[-1])
        state.faults = await c.faults(serial)
        if state.visits_today:
            self._remember_visit(serial, state.visits_today[-1])
        if state.cleans_today:
            self._remember_clean(serial, state.cleans_today[-1])

        if not state.online:  # the EZVIZ proxy cannot reach an offline box
            return state

        state.task = await self._prop(serial, "MachineTask", int)
        state.margin = await self._prop(serial, "LitterMargin", LitterMargin.from_api)

        last = self._settings_at.get(serial)
        if last is None or now - last >= SETTINGS_EVERY:
            read_any = False
            for attr, prop, conv in SETTINGS:
                value = await self._prop(serial, prop, conv)
                if value is not None:
                    setattr(state, attr, value)
                    read_any = True
            try:
                version = await c.version_info(serial)
            except HomerunAuthError:
                raise
            except HomerunError as err:
                _LOGGER.debug("%s: firmware info unavailable: %s", serial, err)
            else:
                state.firmware = version.get("currentVersion") or state.firmware
                state.firmware_latest = version.get("latestVersion") or state.firmware_latest
            if read_any:  # otherwise try again on the next refresh
                self._settings_at[serial] = now
        return state

    def _remember_visit(self, serial: str, visit: ToiletVisit) -> None:
        last = self.last_visit.get(serial)
        if last is None or visit.time >= last.time:
            self.last_visit[serial] = visit

    def _remember_clean(self, serial: str, when: datetime) -> None:
        last = self.last_clean.get(serial)
        if last is None or when >= last:
            self.last_clean[serial] = when

    async def _prop(self, serial: str, name: str, conv: Callable[[Any], Any]) -> Any:
        """One property; a failing property must not hide the rest. None = unknown."""
        try:
            raw = await self.client.get_prop(serial, name)
        except HomerunAuthError:
            raise
        except HomerunError as err:
            _LOGGER.debug("%s: %s unavailable: %s", serial, name, err)
            return None
        if raw is None:
            return None
        try:
            return conv(raw)
        except (TypeError, ValueError):
            _LOGGER.debug("%s: unexpected %s value", serial, name)
            return None

    async def async_command(
        self,
        serial: str,
        call: Awaitable[Any],
        *,
        apply: Callable[[LitterBoxState, Any], None] | None = None,
    ) -> None:
        """Run a write or a command.

        A setting write (`apply` given) is shown at once; the cloud may still return the
        old value for a few seconds, so the settings are re-read on the next regular
        refresh, not right away. A command refreshes now (the task changes).
        """
        try:
            result = await call
        except HomerunAuthError as err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError("homerun token rejected, re-authentication needed") from err
        except (HomerunError, ValueError) as err:
            raise HomeAssistantError(f"homerun command failed: {err}") from err
        if apply is None:
            await self.async_request_refresh()
            return
        if self.data and serial in self.data:
            state = replace(self.data[serial])
            apply(state, result)
            self.async_set_updated_data({**self.data, serial: state})
        self._settings_at.pop(serial, None)
