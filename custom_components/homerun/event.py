"""`cat_visit` event: fired once per new toilet record."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import EVENT_CAT_VISIT
from .coordinator import HomerunConfigEntry, HomerunCoordinator
from .entity import HomerunEntity, to_local


async def async_setup_entry(
    hass: HomeAssistant, entry: HomerunConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(HomerunVisitEvent(coordinator, serial) for serial in coordinator.devices)


class HomerunVisitEvent(HomerunEntity, EventEntity):
    _attr_event_types = [EVENT_CAT_VISIT]

    def __init__(self, coordinator: HomerunCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial, "cat_visit")
        # Visits already in the cloud when HA starts are history, not new events.
        last = coordinator.last_visit.get(serial)
        self._seen: datetime | None = last.time if last else None

    @callback
    def _handle_coordinator_update(self) -> None:
        st = self.state_data
        fired = False
        if st:
            # recent_visits includes yesterday's right after midnight. A visit the cloud
            # backfills with a time older than the last one seen is not reported.
            for visit in st.recent_visits:
                if self._seen is None or visit.time > self._seen:
                    self._trigger_event(
                        EVENT_CAT_VISIT,
                        {
                            "time": to_local(visit.time).isoformat(),
                            "weight_kg": round(visit.weight_g / 1000, 3) if visit.weight_g else None,
                            "duration_s": visit.duration_s,
                        },
                    )
                    self._seen = visit.time
                    # One state write per event, so automations see every visit.
                    self.async_write_ha_state()
                    fired = True
        if not fired:
            super()._handle_coordinator_update()
