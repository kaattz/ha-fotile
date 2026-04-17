"""方太智慧厨房集成 - 按钮实体.

提供:
- 刷新状态: 发送 updateAllStatus 查询全部设备状态
"""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import FotileDevice
from .entity import FotileEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """配置 Button 平台."""
    device: FotileDevice = hass.data[DOMAIN][entry.entry_id]["device"]
    async_add_entities([FotileRefreshButton(device)])


class FotileRefreshButton(FotileEntity, ButtonEntity):
    """刷新状态按钮 — 发送 updateAllStatus 到 service topic."""

    _attr_translation_key = "refresh_status"
    _attr_icon = "mdi:refresh"

    def __init__(self, device: FotileDevice) -> None:
        super().__init__(device)
        self._attr_unique_id = f"{device.device_id}_refresh"

    @property
    def available(self) -> bool:
        """按钮始终可用."""
        return True

    async def async_press(self) -> None:
        """按下按钮 → 查询全部状态."""
        await self.device.async_query_all_status()
