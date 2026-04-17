"""方太智慧厨房集成 - 风机实体.

映射油烟机的风速控制:
- turn_on/off  → PowerSwitchAll
- preset_mode  → WorkMode + FanLevel 组合
- 弱风: WorkMode=1, FanLevel=2
- 强风: WorkMode=1, FanLevel=3
- 自动: WorkMode=2
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
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
    POWER_OFF,
    POWER_ON,
    PRESET_MODE_AUTO,
    PRESET_MODE_HIGH,
    PRESET_MODE_LOW,
    WORK_MODE_AUTO,
    WORK_MODE_MANUAL,
    WORK_MODE_OFF,
)
from .coordinator import FotileDevice
from .entity import FotileEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """配置 Fan 平台."""
    device: FotileDevice = hass.data[DOMAIN][entry.entry_id]["device"]
    async_add_entities([FotileFan(device)])


class FotileFan(FotileEntity, FanEntity):
    """油烟机风速控制实体."""

    _attr_translation_key = "range_hood"
    _attr_supported_features = (
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_preset_modes = [PRESET_MODE_LOW, PRESET_MODE_HIGH, PRESET_MODE_AUTO]
    _attr_speed_count = 2  # 弱风 / 强风

    def __init__(self, device: FotileDevice) -> None:
        super().__init__(device)
        self._attr_unique_id = f"{device.device_id}_fan"

    @property
    def is_on(self) -> bool | None:
        """风机是否运行中."""
        power = self.device.state.get(KEY_POWER)
        if power is None:
            return None
        return power == POWER_ON

    @property
    def preset_mode(self) -> str | None:
        """当前风速模式."""
        work_mode = self.device.state.get(KEY_WORK_MODE)
        fan_level = self.device.state.get(KEY_FAN_LEVEL)

        if work_mode == WORK_MODE_AUTO:
            return PRESET_MODE_AUTO
        if work_mode == WORK_MODE_MANUAL:
            if fan_level == FAN_LEVEL_LOW:
                return PRESET_MODE_LOW
            if fan_level == FAN_LEVEL_HIGH:
                return PRESET_MODE_HIGH
        return None

    @property
    def percentage(self) -> int | None:
        """风速百分比 (0/50/100)."""
        if not self.is_on:
            return 0
        work_mode = self.device.state.get(KEY_WORK_MODE)
        fan_level = self.device.state.get(KEY_FAN_LEVEL)
        if work_mode == WORK_MODE_AUTO:
            return 50  # 自动模式映射到50%
        if work_mode == WORK_MODE_MANUAL:
            if fan_level == FAN_LEVEL_LOW:
                return 50
            if fan_level == FAN_LEVEL_HIGH:
                return 100
        return 0

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """开机. 默认弱风手动挡."""
        if preset_mode:
            await self.async_set_preset_mode(preset_mode)
            return
        # 默认: 开机 + 弱风
        await self.device.async_send_command(
            {KEY_POWER: POWER_ON, KEY_WORK_MODE: WORK_MODE_MANUAL, KEY_FAN_LEVEL: FAN_LEVEL_LOW}
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """关机."""
        await self.device.async_send_command(
            {KEY_POWER: POWER_OFF, KEY_WORK_MODE: WORK_MODE_OFF}
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """切换风速模式."""
        if preset_mode == PRESET_MODE_LOW:
            await self.device.async_send_command(
                {KEY_POWER: POWER_ON, KEY_WORK_MODE: WORK_MODE_MANUAL, KEY_FAN_LEVEL: FAN_LEVEL_LOW}
            )
        elif preset_mode == PRESET_MODE_HIGH:
            await self.device.async_send_command(
                {KEY_POWER: POWER_ON, KEY_WORK_MODE: WORK_MODE_MANUAL, KEY_FAN_LEVEL: FAN_LEVEL_HIGH}
            )
        elif preset_mode == PRESET_MODE_AUTO:
            await self.device.async_send_command(
                {KEY_POWER: POWER_ON, KEY_WORK_MODE: WORK_MODE_AUTO}
            )
