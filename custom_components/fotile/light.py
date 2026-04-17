"""方太智慧厨房集成 - 照明实体.

映射油烟机照明灯:
- Light: 255=开灯, 0=关灯
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    KEY_LIGHT,
    KEY_POWER,
    LIGHT_OFF,
    LIGHT_ON,
    POWER_ON,
)
from .coordinator import FotileDevice
from .entity import FotileEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """配置 Light 平台."""
    device: FotileDevice = hass.data[DOMAIN][entry.entry_id]["device"]
    async_add_entities([FotileLight(device)])


class FotileLight(FotileEntity, LightEntity):
    """油烟机照明灯实体."""

    _attr_translation_key = "hood_light"

    def __init__(self, device: FotileDevice) -> None:
        super().__init__(device)
        self._attr_unique_id = f"{device.device_id}_light"

    @property
    def is_on(self) -> bool | None:
        """灯是否亮着."""
        light = self.device.state.get(KEY_LIGHT)
        if light is None:
            return None
        return light == LIGHT_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """开灯."""
        await self.device.async_send_command(
            {KEY_LIGHT: LIGHT_ON, KEY_POWER: POWER_ON}
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """关灯."""
        await self.device.async_send_command(
            {KEY_LIGHT: LIGHT_OFF, KEY_POWER: POWER_ON}
        )
