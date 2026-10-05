"""Typed views of homerun / EZVIZ otap responses for the CS106-type litter box."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any

DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


class MachineTask(IntEnum):
    """`MachineTask` property (DeviceCatLitterBoxCameraActivity.updateWorkView)."""

    IDLE = 0
    CLEANING = 1
    REFILLING = 2
    LITTER_CLEANING = 3
    LEVELING = 4
    ENTRANCE_UP = 5
    RESETTING = 6
    CAT_INSIDE = 7


def parse_bool(raw: Any) -> bool:
    """Props come back as JSON booleans; tolerate "true"/"false" strings and 0/1."""
    if isinstance(raw, str):
        low = raw.strip().lower()
        if low in ("true", "1"):
            return True
        if low in ("false", "0"):
            return False
        raise ValueError(raw)
    if raw is None:
        raise ValueError("null")
    return bool(raw)


def _opt_int(raw: Any) -> int | None:
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def parse_dt(value: str | None) -> datetime | None:
    """Naive local time as the cloud reports it ("2026-10-05 12:10:44")."""
    if not value:
        return None
    try:
        return datetime.strptime(value, DATETIME_FMT)
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class Device:
    serial: str
    name: str
    categ: str
    status: int
    room: str | None = None
    model: str | None = None

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> Device:
        return cls(
            serial=raw["deviceSerial"],
            name=raw.get("deviceName") or raw["deviceSerial"],
            categ=raw.get("categ") or "",
            status=int(raw.get("status") or 0),
            room=raw.get("roomName"),
            model=raw.get("model"),
        )


@dataclass(frozen=True, slots=True)
class ToiletVisit:
    """One cat visit: weight in grams, duration in seconds."""

    time: datetime
    weight_g: int | None
    duration_s: int | None

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> ToiletVisit | None:
        time = parse_dt(raw.get("dateTime"))
        if time is None:
            return None
        return cls(time=time, weight_g=_opt_int(raw.get("weight")), duration_s=_opt_int(raw.get("duration")))


@dataclass(frozen=True, slots=True)
class AutoClean:
    """`AutoShovel`: clean automatically after the cat leaves, after `delay_min` minutes."""

    enabled: bool
    delay_min: int

    @classmethod
    def from_api(cls, raw: Any) -> AutoClean | None:
        if not isinstance(raw, dict) or "Switch" not in raw:
            return None
        delay = _opt_int(raw.get("time"))
        if delay is None:
            return None
        return cls(enabled=parse_bool(raw["Switch"]), delay_min=delay)

    def to_api(self) -> dict[str, Any]:
        return {"Switch": self.enabled, "time": self.delay_min}


@dataclass(frozen=True, slots=True)
class LitterMargin:
    """`LitterMargin`: True means "enough" / "not full" for each container."""

    refill_bucket_ok: bool | None
    drum_litter_ok: bool | None
    waste_bin_ok: bool | None

    @classmethod
    def from_api(cls, raw: Any) -> LitterMargin | None:
        if not isinstance(raw, dict):
            return None

        def opt(key: str) -> bool | None:
            try:
                return parse_bool(raw[key]) if key in raw else None
            except ValueError:
                return None

        return cls(opt("SandBucket"), opt("Drum"), opt("Dustbin"))


@dataclass(frozen=True, slots=True)
class NightMode:
    """`NightMode`: do-not-disturb window, seconds since midnight."""

    enabled: bool
    start_s: int
    end_s: int

    @classmethod
    def from_api(cls, raw: Any) -> NightMode | None:
        if not isinstance(raw, dict) or "Switch" not in raw:
            return None
        start, end = _opt_int(raw.get("StartTimeInt")), _opt_int(raw.get("EndTimeInt"))
        if start is None or end is None:
            return None
        return cls(enabled=parse_bool(raw["Switch"]), start_s=start, end_s=end)

    def to_api(self) -> dict[str, Any]:
        return {"Switch": self.enabled, "StartTimeInt": self.start_s, "EndTimeInt": self.end_s}


@dataclass(slots=True)
class LitterBoxState:
    """Everything the integration shows for one box. None = not read yet / not supported."""

    online: bool | None = None
    task: int | None = None
    margin: LitterMargin | None = None
    visits_today: list[ToiletVisit] = field(default_factory=list)
    # Visits of today plus, right after midnight, yesterday's: the event entity uses it
    # so a visit between the last poll of the day and 00:00 is not lost.
    recent_visits: list[ToiletVisit] = field(default_factory=list)
    cleans_today: list[datetime] = field(default_factory=list)
    faults: list[str] = field(default_factory=list)
    # Settings (read less often).
    auto_clean: AutoClean | None = None
    child_lock: bool | None = None
    kitten_protection: bool | None = None
    auto_refill: bool | None = None
    auto_burial: bool | None = None
    night_mode: NightMode | None = None
    firmware: str | None = None
    firmware_latest: str | None = None
