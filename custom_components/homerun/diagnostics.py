"""Diagnostics with the token and serials redacted."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_CLIENT_DEVICE_ID, CONF_TOKEN
from .coordinator import HomerunConfigEntry

TO_REDACT = {CONF_TOKEN, CONF_CLIENT_DEVICE_ID}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HomerunConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    boxes = {
        f"box_{i}": asdict(state) for i, state in enumerate((coordinator.data or {}).values())
    }
    return {"entry": async_redact_data(dict(entry.data), TO_REDACT), "boxes": boxes}
