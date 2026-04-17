"""方太智慧厨房集成 - 基础实体类."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .coordinator import FotileDevice


class FotileEntity(Entity):
    """所有方太实体的基类.

    提供:
    - device_info: 将实体归属到同一设备
    - 自动注册 coordinator 监听器
    - _attr_has_entity_name = True (实体名 = 设备名 + 实体名)
    """

    _attr_has_entity_name = True

    def __init__(self, device: FotileDevice) -> None:
        self.device = device

    @property
    def device_info(self) -> DeviceInfo:
        """返回设备信息, 使所有实体归属到同一设备."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id)},
            name=self.device.device_name,
            manufacturer="FOTILE 方太",
            model="智能油烟机",
        )

    @property
    def available(self) -> bool:
        """设备是否可用 — 只要有过状态上报就认为在线."""
        return len(self.device.state) > 0

    async def async_added_to_hass(self) -> None:
        """实体添加到 HA 时注册状态监听."""
        self.async_on_remove(
            self.device.register_listener(self.async_write_ha_state)
        )
