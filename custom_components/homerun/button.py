"""Buttons: clean now, add litter (one portion).

The app offers exactly these on EZVIZ boxes (DataUtils.getCatLitterBoxActionList);
ManualLayingCatLitter answers code 4000 on the CS106, manual deodorization needs a
bound camera module.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import HomerunClient
from .coordinator import HomerunConfigEntry, HomerunCoordinator
from .entity import HomerunControlEntity


@dataclass(frozen=True, kw_only=True)
class HomerunButtonDescription(ButtonEntityDescription):
    press: Callable[[HomerunClient, str], Coroutine[Any, Any, None]]


BUTTONS: tuple[HomerunButtonDescription, ...] = (
    HomerunButtonDescription(key="clean_now", press=lambda c, s: c.clean_now(s)),
    HomerunButtonDescription(key="refill_litter", press=lambda c, s: c.refill_litter(s, 1)),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: HomerunConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        HomerunButton(coordinator, serial, desc) for serial in coordinator.devices for desc in BUTTONS
    )


class HomerunButton(HomerunControlEntity, ButtonEntity):
    entity_description: HomerunButtonDescription

    def __init__(self, coordinator: HomerunCoordinator, serial: str, desc: HomerunButtonDescription) -> None:
        super().__init__(coordinator, serial, desc.key)
        self.entity_description = desc

    async def async_press(self) -> None:
        await self.coordinator.async_command(
            self.serial, self.entity_description.press(self.coordinator.client, self.serial)
        )
