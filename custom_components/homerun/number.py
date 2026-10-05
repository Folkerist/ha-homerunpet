"""Cleaning delay after the cat leaves (`AutoShovel.time`, minutes)."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import AutoClean, LitterBoxState
from .const import CLEAN_DELAY_MAX, CLEAN_DELAY_MIN
from .coordinator import HomerunConfigEntry, HomerunCoordinator
from .entity import HomerunControlEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: HomerunConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(HomerunCleanDelay(coordinator, serial) for serial in coordinator.devices)


class HomerunCleanDelay(HomerunControlEntity, NumberEntity):
    _attr_native_min_value = CLEAN_DELAY_MIN
    _attr_native_max_value = CLEAN_DELAY_MAX
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: HomerunCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial, "clean_delay")

    @property
    def native_value(self) -> int | None:
        st = self.state_data
        return st.auto_clean.delay_min if st and st.auto_clean else None

    async def async_set_native_value(self, value: float) -> None:
        # Read-modify-write in the client: the auto-clean switch stays as the box has it.
        await self.coordinator.async_command(
            self.serial,
            self.coordinator.client.update_auto_clean(self.serial, delay_min=int(value)),
            apply=_set_auto_clean,
        )


def _set_auto_clean(state: LitterBoxState, new: AutoClean) -> None:
    state.auto_clean = new
