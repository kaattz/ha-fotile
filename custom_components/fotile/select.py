"""方太智慧厨房集成 - 风量档位选择器.

独立下拉选择器，映射油烟机风量:
- 关风: WorkMode=0
- 弱风: WorkMode=1, FanLevel=2
- 强风: WorkMode=1, FanLevel=3
- 自动: WorkMode=2
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    FAN_LEVEL_HIGH,
    FAN_LEVEL_LOW,
    KEY_FAN_LEVEL,
    KEY_POWER,
    KEY_WORK_MODE,
    POWER_ON,
    WORK_MODE_AUTO,
    WORK_MODE_MANUAL,
    WORK_MODE_OFF,
)
from .coordinator import FotileDevice
from .entity import FotileEntity

OPT_OFF = "关风"
OPT_LOW = "弱风"
OPT_HIGH = "强风"
OPT_AUTO = "自动"

OPTIONS = [OPT_OFF, OPT_LOW, OPT_HIGH, OPT_AUTO]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """配置 Select 平台."""
    device: FotileDevice = hass.data[DOMAIN][entry.entry_id]["device"]
    async_add_entities([FotileFanLevelSelect(device)])


class FotileFanLevelSelect(FotileEntity, SelectEntity):
    """风量档位选择器."""

    _attr_translation_key = "fan_level"
    _attr_options = OPTIONS
    _attr_icon = "mdi:fan"

    def __init__(self, device: FotileDevice) -> None:
        super().__init__(device)
        self._attr_unique_id = f"{device.device_id}_fan_level"

    @property
    def current_option(self) -> str | None:
        """当前风量档位."""
        work_mode = self.device.state.get(KEY_WORK_MODE)
        fan_level = self.device.state.get(KEY_FAN_LEVEL)

        if work_mode is None:
            return None

        work_mode = int(work_mode)
        if work_mode == WORK_MODE_OFF:
            return OPT_OFF
        if work_mode == WORK_MODE_AUTO:
            return OPT_AUTO
        if work_mode == WORK_MODE_MANUAL:
            if fan_level is not None:
                fan_level = int(fan_level)
                if fan_level == FAN_LEVEL_HIGH:
                    return OPT_HIGH
                if fan_level == FAN_LEVEL_LOW:
                    return OPT_LOW
            return OPT_LOW  # 手动挡缺省弱风
        return None

    async def async_select_option(self, option: str) -> None:
        """切换风量档位."""
        if option == OPT_OFF:
            await self.device.async_send_command(
                {KEY_POWER: POWER_ON, KEY_WORK_MODE: WORK_MODE_OFF}
            )
        elif option == OPT_LOW:
            await self.device.async_send_command(
                {KEY_POWER: POWER_ON, KEY_WORK_MODE: WORK_MODE_MANUAL, KEY_FAN_LEVEL: FAN_LEVEL_LOW}
            )
        elif option == OPT_HIGH:
            await self.device.async_send_command(
                {KEY_POWER: POWER_ON, KEY_WORK_MODE: WORK_MODE_MANUAL, KEY_FAN_LEVEL: FAN_LEVEL_HIGH}
            )
        elif option == OPT_AUTO:
            await self.device.async_send_command(
                {KEY_POWER: POWER_ON, KEY_WORK_MODE: WORK_MODE_AUTO}
            )
