"""Switches for the box settings."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import HomerunClient, LitterBoxState
from .coordinator import HomerunConfigEntry, HomerunCoordinator
from .entity import HomerunControlEntity


@dataclass(frozen=True, kw_only=True)
class HomerunSwitchDescription(SwitchEntityDescription):
    value: Callable[[LitterBoxState], bool | None]
    # (client, serial, on) -> write; its result goes to `apply`
    write: Callable[[HomerunClient, str, bool], Coroutine[Any, Any, Any]]
    apply: Callable[[LitterBoxState, Any, bool], None]


def _plain(prop: str, attr: str) -> dict[str, Any]:
    """A boolean property written as `true` / `false`."""
    return {
        "value": lambda st: getattr(st, attr),
        "write": lambda c, s, on: c.set_prop(s, prop, on),
        "apply": lambda st, _result, on: setattr(st, attr, on),
    }


SWITCHES: tuple[HomerunSwitchDescription, ...] = (
    HomerunSwitchDescription(
        key="auto_clean",
        value=lambda st: st.auto_clean.enabled if st.auto_clean else None,
        # Read-modify-write: the delay stays as the box has it.
        write=lambda c, s, on: c.update_auto_clean(s, enabled=on),
        apply=lambda st, new, _on: setattr(st, "auto_clean", new),
    ),
    HomerunSwitchDescription(
        key="night_mode",
        entity_category=EntityCategory.CONFIG,
        value=lambda st: st.night_mode.enabled if st.night_mode else None,
        # Read-modify-write: the night window stays as the box has it.
        write=lambda c, s, on: c.update_night_mode(s, enabled=on),
        apply=lambda st, new, _on: setattr(st, "night_mode", new),
    ),
    HomerunSwitchDescription(
        key="child_lock", entity_category=EntityCategory.CONFIG, **_plain("ChildLock", "child_lock")
    ),
    HomerunSwitchDescription(
        key="kitten_protection",
        entity_category=EntityCategory.CONFIG,
        **_plain("KittenProtection", "kitten_protection"),
    ),
    HomerunSwitchDescription(
        key="auto_refill",
        entity_category=EntityCategory.CONFIG,
        **_plain("AutomaticSandAddingSwitch", "auto_refill"),
    ),
    HomerunSwitchDescription(
        key="auto_burial",
        entity_category=EntityCategory.CONFIG,
        **_plain("AutomaticBurial", "auto_burial"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: HomerunConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        HomerunSwitch(coordinator, serial, desc) for serial in coordinator.devices for desc in SWITCHES
    )


class HomerunSwitch(HomerunControlEntity, SwitchEntity):
    entity_description: HomerunSwitchDescription

    def __init__(self, coordinator: HomerunCoordinator, serial: str, desc: HomerunSwitchDescription) -> None:
        super().__init__(coordinator, serial, desc.key)
        self.entity_description = desc

    @property
    def is_on(self) -> bool | None:
        st = self.state_data
        return self.entity_description.value(st) if st else None

    async def _write(self, on: bool) -> None:
        desc = self.entity_description
        await self.coordinator.async_command(
            self.serial,
            desc.write(self.coordinator.client, self.serial, on),
            apply=lambda st, result: desc.apply(st, result, on),
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._write(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._write(False)
