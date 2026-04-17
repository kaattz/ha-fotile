"""方太智慧厨房集成 - 升降面板实体.

映射油烟机升降面板:
- CtlUpDown: 1=升, 2=降, 0=暂停
- UpDownPosition: 0=最高位置, 100=最低位置
  注意: HA Cover 的 position 定义是 0=关(最低), 100=开(最高),
  与方太协议相反, 需要做 100-x 转换。
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CTL_DOWN,
    CTL_STOP,
    CTL_UP,
    DOMAIN,
    KEY_CTL_UP_DOWN,
    KEY_UP_DOWN_POSITION,
)
from .coordinator import FotileDevice
from .entity import FotileEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """配置 Cover 平台."""
    device: FotileDevice = hass.data[DOMAIN][entry.entry_id]["device"]
    async_add_entities([FotileCover(device)])


class FotileCover(FotileEntity, CoverEntity):
    """油烟机升降面板实体."""

    _attr_translation_key = "hood_lift"
    _attr_device_class = CoverDeviceClass.DAMPER
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
    )

    def __init__(self, device: FotileDevice) -> None:
        super().__init__(device)
        self._attr_unique_id = f"{device.device_id}_cover"

    @property
    def current_cover_position(self) -> int | None:
        """当前面板位置.

        方太: 0=最高(全开), 100=最低(全关)
        HA:   0=全关, 100=全开
        转换: ha_pos = 100 - fotile_pos
        """
        pos = self.device.state.get(KEY_UP_DOWN_POSITION)
        if pos is None:
            return None
        return 100 - int(pos)

    @property
    def is_closed(self) -> bool | None:
        """面板是否在最低位(关闭)."""
        pos = self.current_cover_position
        if pos is None:
            return None
        return pos == 0

    async def async_open_cover(self, **kwargs: Any) -> None:
        """升起面板."""
        await self.device.async_send_command({KEY_CTL_UP_DOWN: CTL_UP})

    async def async_close_cover(self, **kwargs: Any) -> None:
        """降下面板."""
        await self.device.async_send_command({KEY_CTL_UP_DOWN: CTL_DOWN})

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """暂停升降."""
        await self.device.async_send_command({KEY_CTL_UP_DOWN: CTL_STOP})
