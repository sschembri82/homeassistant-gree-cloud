"""Extra read-only Hot Water Heat Pump (HWHP) readings (sschembri82 fork).

The HWHP pushes its whole property set on the ``status`` MQTT topic about
every 70 s, and the library merges it into ``raw_properties``. The upstream
integration reads only a handful of those keys; this module surfaces more of
them as sensors and binary sensors (davo22/homeassistant-gree-cloud#74).

Kept in its own module so upstream merges touch as little shared code as
possible. Everything here is read-only: nothing is ever sent to the device.

Raw encodings seen on a Gree "Hombask" 206 L unit (ModelType 30729,
mid 910004, firmware V3.2.M), 2026-11-10:
- temperatures: raw - 100 = degrees C (e.g. outTemp 124 -> 24 C). A raw 0
  means "no such sensor fitted" (centralTemp reads 0), so it is skipped.
- flags: 0/1.
- timers: WtmrNStartHr/Min, WtmrNEndHr/Min with SchN = 1 when enabled. Timer
  1 matched the Gree+ app (10:30-14:00, enabled).
- eleDay/heatDay/... arrays are all zero while ConsumeDisplayEn is 0 (the
  unit has no consumption metering enabled), so they are not exposed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTemperature

from .const import HWHP_TEMP_ENCODING_OFFSET

# Raw keys -------------------------------------------------------------------
TEMP_PROPS: dict[str, str] = {
    # key: translation_key
    "upperTemp": "hwhp_upper_temperature",
    "bottomTemp": "hwhp_bottom_temperature",
    "outTemp": "hwhp_outdoor_temperature",
    "exhaustTemp1": "hwhp_exhaust_temperature",
    "outHeatExchangTemp": "hwhp_outdoor_coil_temperature",
    "intankPipeTemp": "hwhp_tank_coil_temperature",
}

FLAG_PROPS: dict[str, tuple[str, BinarySensorDeviceClass | None]] = {
    # key: (translation_key, device_class). Meanings are read from the key
    # names; check them against a heating run before relying on them.
    "compEng1Flag": ("hwhp_compressor", BinarySensorDeviceClass.RUNNING),
    "outFanHigFlag": ("hwhp_fan_high", BinarySensorDeviceClass.RUNNING),
    "outFanLowFlag": ("hwhp_fan_low", BinarySensorDeviceClass.RUNNING),
    "auxiHeatFlag": ("hwhp_electric_heater", BinarySensorDeviceClass.HEAT),
    "fourWay1Flag": ("hwhp_defrost", None),
    "DisinfectStatus": ("hwhp_disinfecting", BinarySensorDeviceClass.RUNNING),
}

ERROR_PROPS = ("AllErr", "ErrHeat", "JFerr", "BwErr")

EEV_PROP = "valueEEV1"

TIMERS = (
    # (translation_key, enabled key, start hr, start min, end hr, end min)
    ("hwhp_timer_1", "Sch1", "Wtmr1StartHr", "Wtmr1StartMin", "Wtmr1EndHr", "Wtmr1EndMin"),
    ("hwhp_timer_2", "Sch2", "Wtmr2StartHr", "Wtmr2StartMin", "Wtmr2EndHr", "Wtmr2EndMin"),
)

# Asked for on every poll as well, so values exist at startup and stay fresh
# if the periodic push stops. Appended after the upstream columns.
POLL_PROPS: list[str] = [
    *TEMP_PROPS,
    *FLAG_PROPS,
    *ERROR_PROPS,
    EEV_PROP,
    *(k for t in TIMERS for k in t[1:]),
]


def _int(props: dict[str, Any], key: str) -> int | None:
    raw = props.get(key)
    if isinstance(raw, bool) or not isinstance(raw, int):
        return None
    return raw


def temperature(props: dict[str, Any], key: str) -> int | None:
    """Return degrees C for a +100-encoded temperature, None if absent or 0."""
    raw = _int(props, key)
    if raw is None or raw <= 0:
        return None
    return raw - HWHP_TEMP_ENCODING_OFFSET


def flag(props: dict[str, Any], key: str) -> bool | None:
    raw = _int(props, key)
    return None if raw is None else raw != 0


def timer(props: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    """Return 'HH:MM-HH:MM' for an enabled timer, 'off' when disabled."""
    enabled, sh, sm, eh, em = keys
    vals = [_int(props, k) for k in (enabled, sh, sm, eh, em)]
    if any(v is None for v in vals):
        return None
    if vals[0] == 0:
        return "off"
    return f"{vals[1]:02d}:{vals[2]:02d}-{vals[3]:02d}:{vals[4]:02d}"


def error_codes(props: dict[str, Any]) -> dict[str, int | None]:
    return {k: _int(props, k) for k in ERROR_PROPS}


# Entity descriptions ----------------------------------------------------------
@dataclass(kw_only=True, frozen=True)
class HWHPSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]


@dataclass(kw_only=True, frozen=True)
class HWHPBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], bool | None]
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def _temp_desc(key: str, translation_key: str) -> HWHPSensorDescription:
    return HWHPSensorDescription(
        key=f"hwhp_{key}",
        translation_key=translation_key,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda p, k=key: temperature(p, k),
    )


def _timer_desc(t: tuple[str, ...]) -> HWHPSensorDescription:
    return HWHPSensorDescription(
        key=t[0],
        translation_key=t[0],
        icon="mdi:timer-outline",
        value_fn=lambda p, keys=t[1:]: timer(p, keys),
    )


HWHP_SENSORS: tuple[HWHPSensorDescription, ...] = (
    *(_temp_desc(k, tk) for k, tk in TEMP_PROPS.items()),
    HWHPSensorDescription(
        key=f"hwhp_{EEV_PROP}",
        translation_key="hwhp_expansion_valve",
        icon="mdi:valve",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda p: _int(p, EEV_PROP),
    ),
    *(_timer_desc(t) for t in TIMERS),
)

HWHP_BINARY_SENSORS: tuple[HWHPBinarySensorDescription, ...] = (
    *(
        HWHPBinarySensorDescription(
            key=f"hwhp_{k}",
            translation_key=tk,
            device_class=dc,
            value_fn=lambda p, k=k: flag(p, k),
        )
        for k, (tk, dc) in FLAG_PROPS.items()
    ),
    HWHPBinarySensorDescription(
        key="hwhp_fault",
        translation_key="hwhp_fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda p: (
            None
            if all(v is None for v in error_codes(p).values())
            else any(v for v in error_codes(p).values())
        ),
        attrs_fn=error_codes,
    ),
)
