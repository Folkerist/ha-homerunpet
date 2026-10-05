"""Sensors: task, visits, cat weight, last cleaning, fault."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfMass, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import LitterBoxState, MachineTask
from .coordinator import HomerunConfigEntry, HomerunCoordinator
from .entity import HomerunEntity, to_local

TASK_OPTIONS = [t.name.lower() for t in MachineTask]


def _local(value: datetime | None) -> datetime | None:
    return to_local(value) if value else None


@dataclass(frozen=True, kw_only=True)
class HomerunSensorDescription(SensorEntityDescription):
    value: Callable[[HomerunCoordinator, str, LitterBoxState], Any]
    attrs: Callable[[HomerunCoordinator, str, LitterBoxState], dict[str, Any]] | None = None


def _task(_c: HomerunCoordinator, _s: str, st: LitterBoxState) -> str | None:
    if st.task is None:
        return None
    try:
        return MachineTask(st.task).name.lower()
    except ValueError:
        return None


def _last_visit(c: HomerunCoordinator, s: str):
    return c.last_visit.get(s)


SENSORS: tuple[HomerunSensorDescription, ...] = (
    HomerunSensorDescription(
        key="task",
        device_class=SensorDeviceClass.ENUM,
        options=TASK_OPTIONS,
        value=_task,
    ),
    HomerunSensorDescription(
        key="visits_today",
        # Resets at midnight: TOTAL_INCREASING treats the drop as a new cycle.
        state_class=SensorStateClass.TOTAL_INCREASING,
        value=lambda c, s, st: len(st.visits_today),
        attrs=lambda c, s, st: {
            "visits": [
                {"time": to_local(v.time).isoformat(), "weight_g": v.weight_g, "duration_s": v.duration_s}
                for v in st.visits_today
            ]
        },
    ),
    HomerunSensorDescription(
        key="last_visit",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda c, s, st: _local(v.time) if (v := _last_visit(c, s)) else None,
    ),
    HomerunSensorDescription(
        key="cat_weight",
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        suggested_display_precision=2,
        value=lambda c, s, st: (
            round(v.weight_g / 1000, 3) if (v := _last_visit(c, s)) and v.weight_g else None
        ),
    ),
    HomerunSensorDescription(
        key="visit_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value=lambda c, s, st: v.duration_s if (v := _last_visit(c, s)) else None,
    ),
    HomerunSensorDescription(
        key="cleanings_today",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value=lambda c, s, st: len(st.cleans_today),
    ),
    HomerunSensorDescription(
        key="last_clean",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda c, s, st: _local(c.last_clean.get(s)),
    ),
    HomerunSensorDescription(
        key="faults",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda c, s, st: len(st.faults),
        # App localisation keys, e.g. catLitterBox_text_sandSiloCleaning.
        attrs=lambda c, s, st: {"codes": st.faults},
    ),
    HomerunSensorDescription(
        key="firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda c, s, st: st.firmware,
        attrs=lambda c, s, st: {"latest": st.firmware_latest},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: HomerunConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        HomerunSensor(coordinator, serial, desc) for serial in coordinator.devices for desc in SENSORS
    )


class HomerunSensor(HomerunEntity, SensorEntity):
    entity_description: HomerunSensorDescription
    _unrecorded_attributes = frozenset({"visits", "codes", "latest"})

    def __init__(self, coordinator: HomerunCoordinator, serial: str, desc: HomerunSensorDescription) -> None:
        super().__init__(coordinator, serial, desc.key)
        self.entity_description = desc

    @property
    def native_value(self) -> Any:
        st = self.state_data
        return self.entity_description.value(self.coordinator, self.serial, st) if st else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        st = self.state_data
        if st is None or self.entity_description.attrs is None:
            return None
        return self.entity_description.attrs(self.coordinator, self.serial, st)
