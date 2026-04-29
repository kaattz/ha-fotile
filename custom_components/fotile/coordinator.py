"""方太智慧厨房集成 - MQTT 通信协调器.

管理与油烟机之间的 MQTT 消息收发和设备状态。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, callback

from .const import (
    TOPIC_CONTROL,
    TOPIC_REPLY,
    TOPIC_SYNC,
)

_LOGGER = logging.getLogger(__name__)


class FotileDevice:
    """油烟机 MQTT 通信协调器.

    职责:
    - 订阅 sync/{device_id}/# 接收设备状态
    - 订阅 reply/{device_id}/# 接收服务应答
    - 发布 control/{device_id}/{serial} 下发控制指令
    - 维护 state 字典供各实体读取
    """

    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        device_serial: str,
        device_name: str,
    ) -> None:
        self.hass = hass
        self.device_id = device_id
        self.device_serial = device_serial
        self.device_name = device_name

        # 设备当前状态 (键名来自 MQTT Payload JSON)
        self.state: dict[str, Any] = {}

        # 实体监听回调列表
        self._listeners: list[Callable[[], None]] = []

        # MQTT 取消订阅函数
        self._unsub_sync: Callable | None = None
        self._unsub_reply: Callable | None = None

        # Topic 实例化
        self._topic_sync = TOPIC_SYNC.format(device_id=device_id)
        self._topic_control = TOPIC_CONTROL.format(
            device_id=device_id, device_serial=device_serial
        )
        self._topic_reply = TOPIC_REPLY.format(device_id=device_id)

    # ── 生命周期 ──────────────────────────────────────────────────

    async def async_setup(self) -> None:
        """订阅 MQTT Topic, 开始监听设备状态."""
        self._unsub_sync = await mqtt.async_subscribe(
            self.hass,
            self._topic_sync,
            self._handle_sync_message,
            qos=1,
        )
        self._unsub_reply = await mqtt.async_subscribe(
            self.hass,
            self._topic_reply,
            self._handle_reply_message,
            qos=1,
        )
        _LOGGER.info(
            "MQTT 订阅已建立: sync=%s, reply=%s",
            self._topic_sync,
            self._topic_reply,
        )

        # 启动后主动查询一次全部状态
        await self.async_query_all_status()

    async def async_teardown(self) -> None:
        """取消 MQTT 订阅."""
        if self._unsub_sync:
            self._unsub_sync()
            self._unsub_sync = None
        if self._unsub_reply:
            self._unsub_reply()
            self._unsub_reply = None
        _LOGGER.info("MQTT 订阅已取消")

    # ── MQTT 消息处理 ─────────────────────────────────────────────

    @callback
    def _handle_sync_message(self, msg: mqtt.ReceiveMessage) -> None:
        """处理 sync 消息 — 设备状态上报."""
        try:
            payload = json.loads(msg.payload)
        except (json.JSONDecodeError, TypeError):
            _LOGGER.warning("sync 消息解析失败: topic=%s, payload=%s", msg.topic, msg.payload)
            return

        if not isinstance(payload, dict):
            _LOGGER.warning("sync 消息格式异常 (非 dict): %s", payload)
            return

        _LOGGER.debug("sync 状态更新: %s", payload)
        self.state.update(payload)
        self._notify_listeners()

    @callback
    def _handle_reply_message(self, msg: mqtt.ReceiveMessage) -> None:
        """处理 reply 消息 — 服务查询应答 (通常包含完整状态)."""
        try:
            payload = json.loads(msg.payload)
        except (json.JSONDecodeError, TypeError):
            _LOGGER.warning("reply 消息解析失败: topic=%s, payload=%s", msg.topic, msg.payload)
            return

        if not isinstance(payload, dict):
            return

        _LOGGER.debug("reply 状态更新: %s", payload)
        self.state.update(payload)
        self._notify_listeners()

    # ── 发送指令 ──────────────────────────────────────────────────

    async def async_send_command(self, command: dict[str, Any]) -> None:
        """发送控制指令到油烟机.

        Args:
            command: JSON 键值对, 如 {"PowerSwitchAll": 2, "WorkMode": 1}
        """
        payload = json.dumps(command)
        _LOGGER.info("发送控制指令: topic=%s, payload=%s", self._topic_control, payload)
        await mqtt.async_publish(
            self.hass,
            self._topic_control,
            payload,
            qos=1,
        )

    async def async_query_all_status(self) -> None:
        """发送 updateAllStatus 查询, 刷新全部设备状态."""
        payload = json.dumps({"updateAllStatus": None})
        _LOGGER.info("查询全部状态: topic=%s", self._topic_control)
        await mqtt.async_publish(
            self.hass,
            self._topic_control,
            payload,
            qos=1,
        )

    # ── 监听器管理 ────────────────────────────────────────────────

    @callback
    def register_listener(self, update_callback: Callable[[], None]) -> Callable[[], None]:
        """注册状态变更监听器, 返回取消注册函数.

        实体在 async_added_to_hass 中调用此方法,
        当 MQTT 状态更新时会触发 async_write_ha_state.
        """
        self._listeners.append(update_callback)

        @callback
        def remove_listener() -> None:
            self._listeners.remove(update_callback)

        return remove_listener

    @callback
    def _notify_listeners(self) -> None:
        """通知所有注册的监听器."""
        for update_callback in self._listeners:
            update_callback()
