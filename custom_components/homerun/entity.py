"""Base entity: one HA device per litter box."""

from __future__ import annotations

from datetime import datetime

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .api import LitterBoxState
from .const import DOMAIN, MANUFACTURER
from .coordinator import HomerunCoordinator


def to_local(value: datetime) -> datetime:
    """The cloud reports naive time in the phone's zone (the app sends X-Client-Time-Zone);
    the integration sends HA's zone, so the naive value is HA local time.
    """
    return value.replace(tzinfo=dt_util.get_default_time_zone())


class HomerunEntity(CoordinatorEntity[HomerunCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: HomerunCoordinator, serial: str, key: str) -> None:
        super().__init__(coordinator)
        self.serial = serial
        self._attr_unique_id = f"{serial}_{key}"
        self._attr_translation_key = key
        dev = coordinator.devices[serial]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer=MANUFACTURER,
            model=dev.model or "Litter box",
            name=dev.name,
            suggested_area=dev.room,
            serial_number=serial,
        )

    @property
    def state_data(self) -> LitterBoxState | None:
        return (self.coordinator.data or {}).get(self.serial)

    @property
    def available(self) -> bool:
        return super().available and self.state_data is not None


class HomerunControlEntity(HomerunEntity):
    """Settings and commands need the box online (the cloud relays them to it)."""

    @property
    def available(self) -> bool:
        return super().available and bool(self.state_data and self.state_data.online)
