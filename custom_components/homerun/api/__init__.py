"""homerunPET (霍曼宠物) cloud client, independent of Home Assistant."""

from .client import HomerunClient
from .exceptions import HomerunApiError, HomerunAuthError, HomerunConnectionError, HomerunError
from .models import (
    AutoClean,
    Device,
    LitterBoxState,
    LitterMargin,
    MachineTask,
    NightMode,
    ToiletVisit,
)

__all__ = [
    "AutoClean",
    "Device",
    "HomerunApiError",
    "HomerunAuthError",
    "HomerunClient",
    "HomerunConnectionError",
    "HomerunError",
    "LitterBoxState",
    "LitterMargin",
    "MachineTask",
    "NightMode",
    "ToiletVisit",
]
