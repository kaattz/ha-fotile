"""方太智慧厨房集成 - 传感器实体.

只读传感器:
- AirStewardAirQuality: 空气质量指数
- RunningTime: 累计运行时间
- UpDownPosition: 升降面板当前位置
"""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    KEY_AIR_QUALITY,
    KEY_RUNNING_TIME,
    KEY_UP_DOWN_POSITION,
)
from .coordinator import FotileDevice
from .entity import FotileEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """配置 Sensor 平台."""
    device: FotileDevice = hass.data[DOMAIN][entry.entry_id]["device"]
    async_add_entities([
        FotileAirQualitySensor(device),
        FotileRunningTimeSensor(device),
        FotileLiftPositionSensor(device),
    ])


class FotileAirQualitySensor(FotileEntity, SensorEntity):
    """空气质量传感器."""

    _attr_translation_key = "air_quality"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:air-filter"

    def __init__(self, device: FotileDevice) -> None:
        super().__init__(device)
        self._attr_unique_id = f"{device.device_id}_air_quality"

    @property
    def native_value(self) -> int | None:
        """空气质量数值."""
        return self.device.state.get(KEY_AIR_QUALITY)


class FotileRunningTimeSensor(FotileEntity, SensorEntity):
    """累计运行时间传感器."""

    _attr_translation_key = "running_time"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "min"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_icon = "mdi:timer-outline"

    def __init__(self, device: FotileDevice) -> None:
        super().__init__(device)
        self._attr_unique_id = f"{device.device_id}_running_time"

    @property
    def native_value(self) -> int | None:
        """累计运行时间 (分钟)."""
        return self.device.state.get(KEY_RUNNING_TIME)


class FotileLiftPositionSensor(FotileEntity, SensorEntity):
    """升降面板位置传感器 (原始值: 0=最高, 100=最低)."""

    _attr_translation_key = "lift_position"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:arrow-up-down"

    def __init__(self, device: FotileDevice) -> None:
        super().__init__(device)
        self._attr_unique_id = f"{device.device_id}_lift_position"

    @property
    def native_value(self) -> int | None:
        """升降位置 (0~100)."""
        return self.device.state.get(KEY_UP_DOWN_POSITION)
