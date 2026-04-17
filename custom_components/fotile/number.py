"""方太智慧厨房集成 - 延时关机实体.

映射延时关机时间设置:
- DelayTime: N (单位: 分钟)
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, KEY_DELAY_TIME
from .coordinator import FotileDevice
from .entity import FotileEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """配置 Number 平台."""
    device: FotileDevice = hass.data[DOMAIN][entry.entry_id]["device"]
    async_add_entities([FotileDelayTimer(device)])


class FotileDelayTimer(FotileEntity, NumberEntity):
    """延时关机时间设置."""

    _attr_translation_key = "delay_timer"
    _attr_native_min_value = 0
    _attr_native_max_value = 30
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "min"
    _attr_mode = NumberMode.SLIDER

    def __init__(self, device: FotileDevice) -> None:
        super().__init__(device)
        self._attr_unique_id = f"{device.device_id}_delay_timer"

    @property
    def native_value(self) -> float | None:
        """当前延时时间 (分钟)."""
        value = self.device.state.get(KEY_DELAY_TIME)
        if value is None:
            return None
        return float(value)

    async def async_set_native_value(self, value: float) -> None:
        """设置延时关机时间."""
        await self.device.async_send_command({KEY_DELAY_TIME: int(value)})
