"""方太智慧厨房集成 - 开关实体.

映射油烟机升降锁定:
- UpDownLock: 1=锁定, 0=不锁定
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    KEY_UP_DOWN_LOCK,
    LOCK_OFF,
    LOCK_ON,
)
from .coordinator import FotileDevice
from .entity import FotileEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """配置 Switch 平台."""
    device: FotileDevice = hass.data[DOMAIN][entry.entry_id]["device"]
    async_add_entities([FotileLiftLock(device)])


class FotileLiftLock(FotileEntity, SwitchEntity):
    """升降锁定开关."""

    _attr_translation_key = "lift_lock"
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, device: FotileDevice) -> None:
        super().__init__(device)
        self._attr_unique_id = f"{device.device_id}_lift_lock"

    @property
    def is_on(self) -> bool | None:
        """锁定状态."""
        lock = self.device.state.get(KEY_UP_DOWN_LOCK)
        if lock is None:
            return None
        return lock == LOCK_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """锁定升降."""
        await self.device.async_send_command({KEY_UP_DOWN_LOCK: LOCK_ON})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """解锁升降."""
        await self.device.async_send_command({KEY_UP_DOWN_LOCK: LOCK_OFF})
