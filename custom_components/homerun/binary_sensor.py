"""Binary sensors: online, waste bin full, litter low, fault."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import LitterBoxState
from .coordinator import HomerunConfigEntry, HomerunCoordinator
from .entity import HomerunEntity


def _not(value: bool | None) -> bool | None:
    return None if value is None else not value


@dataclass(frozen=True, kw_only=True)
class HomerunBinaryDescription(BinarySensorEntityDescription):
    value: Callable[[LitterBoxState], bool | None]


BINARY_SENSORS: tuple[HomerunBinaryDescription, ...] = (
    HomerunBinaryDescription(
        key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda st: st.online,
    ),
    HomerunBinaryDescription(
        key="waste_bin_full",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value=lambda st: _not(st.margin.waste_bin_ok) if st.margin else None,
    ),
    HomerunBinaryDescription(
        key="litter_reservoir_low",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value=lambda st: _not(st.margin.refill_bucket_ok) if st.margin else None,
    ),
    HomerunBinaryDescription(
        key="drum_litter_low",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value=lambda st: _not(st.margin.drum_litter_ok) if st.margin else None,
    ),
    HomerunBinaryDescription(
        key="has_fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value=lambda st: bool(st.faults),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: HomerunConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        HomerunBinarySensor(coordinator, serial, desc)
        for serial in coordinator.devices
        for desc in BINARY_SENSORS
    )


class HomerunBinarySensor(HomerunEntity, BinarySensorEntity):
    entity_description: HomerunBinaryDescription

    def __init__(self, coordinator: HomerunCoordinator, serial: str, desc: HomerunBinaryDescription) -> None:
        super().__init__(coordinator, serial, desc.key)
        self.entity_description = desc

    @property
    def is_on(self) -> bool | None:
        st = self.state_data
        return self.entity_description.value(st) if st else None
