"""方太智慧厨房集成 - UI 配置流程."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Any

import voluptuous as vol

from homeassistant.components import network
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_SERIAL,
    CONF_MQTT_HOST,
    CONF_MQTT_PORT,
    CONF_PROXY_PORT,
    DEFAULT_MQTT_PORT,
    DEFAULT_PROXY_PORT,
    DOMAIN,
)
from .proxy import FotileProxy

_LOGGER = logging.getLogger(__name__)

DISCOVERY_TIMEOUT = 180


def _build_user_schema(default_mqtt_host: str) -> vol.Schema:
    """构建配置表单，默认指向 HA 主机上的 EMQX add-on."""
    return vol.Schema(
        {
            vol.Required(CONF_MQTT_HOST, default=default_mqtt_host): str,
            vol.Required(CONF_MQTT_PORT, default=DEFAULT_MQTT_PORT): int,
            vol.Optional(CONF_PROXY_PORT, default=DEFAULT_PROXY_PORT): int,
        }
    )


class FotileConfigFlow(ConfigFlow, domain=DOMAIN):
    """方太油烟机配置流程.

    收集信息:
    - mqtt_host:        MQTT Broker 局域网 IP (默认 HA 主机 IP)
    - mqtt_port:        MQTT Broker 端口 (默认 1883)
    - proxy_port:       本地最小云 HTTP 端口 (默认 80)
    """

    VERSION = 1

    def __init__(self) -> None:
        """初始化发现状态."""
        super().__init__()
        self._base_data: dict[str, Any] = {}
        self._discovered: dict[str, str] = {}
        self._discovery_event: asyncio.Event | None = None
        self._discovery_task: asyncio.Task | None = None
        self._discovery_proxy: FotileProxy | None = None
        self._discovery_error: str | None = None

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """用户配置步骤."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # 校验 MQTT host 非空
            mqtt_host = user_input[CONF_MQTT_HOST].strip()
            if not mqtt_host:
                errors[CONF_MQTT_HOST] = "invalid_mqtt_host"

            mqtt_port = user_input[CONF_MQTT_PORT]
            if mqtt_port < 1 or mqtt_port > 65535:
                errors[CONF_MQTT_PORT] = "invalid_port"

            # 校验端口范围
            port = user_input[CONF_PROXY_PORT]
            if port < 1 or port > 65535:
                errors[CONF_PROXY_PORT] = "invalid_port"

            if not errors:
                self._base_data = {
                    CONF_MQTT_HOST: mqtt_host,
                    CONF_MQTT_PORT: mqtt_port,
                    CONF_PROXY_PORT: port,
                }
                self._discovered = {}
                self._discovery_task = None
                self._discovery_error = None
                return await self.async_step_discovery()

        return self.async_show_form(
            step_id="user",
            data_schema=_build_user_schema(await self._async_default_mqtt_host()),
            errors=errors,
        )

    async def async_step_discovery(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """等待烟机启动请求本地云，从请求中自动发现设备身份."""
        if self._discovery_task is None:
            self._discovery_task = self.hass.async_create_task(
                self._async_discover_device()
            )

        if not self._discovery_task.done():
            return self.async_show_progress(
                progress_action="discover_device",
                progress_task=self._discovery_task,
            )

        return self.async_show_progress_done(next_step_id="finish")

    async def async_step_finish(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """发现完成后创建配置项."""
        if self._discovery_task is not None and not self._discovery_task.done():
            return await self.async_step_discovery()

        if self._discovery_task is not None:
            with suppress(asyncio.CancelledError):
                task_error = self._discovery_task.exception()
                if task_error is not None and self._discovery_error is None:
                    _LOGGER.warning("方太烟机自动发现失败: %s", task_error)
                    self._discovery_error = "cannot_start_discovery"

        await self._async_stop_discovery_proxy()

        if self._discovery_error is not None:
            return self.async_abort(reason=self._discovery_error)

        if not self._discovery_ready:
            return self.async_abort(reason="discovery_timeout")

        device_id = self._discovered[CONF_DEVICE_ID]
        device_serial = self._discovered[CONF_DEVICE_SERIAL]

        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"Fotile {device_id[:8]}...",
            data={
                CONF_DEVICE_ID: device_id,
                CONF_DEVICE_SERIAL: device_serial,
                **self._base_data,
            },
        )

    async def _async_discover_device(self) -> None:
        """启动临时本地云，直到抓到 device_id 和 device_serial."""
        self._discovery_event = asyncio.Event()
        self._discovery_proxy = FotileProxy(
            mqtt_host=self._base_data[CONF_MQTT_HOST],
            device_id=None,
            port=self._base_data[CONF_PROXY_PORT],
            device_serial=None,
            mqtt_port=self._base_data[CONF_MQTT_PORT],
            on_device_info=self._handle_device_info,
        )

        try:
            await self._discovery_proxy.async_start()
            await asyncio.wait_for(self._discovery_event.wait(), DISCOVERY_TIMEOUT)
        except TimeoutError:
            self._discovery_error = "discovery_timeout"
            await self._async_stop_discovery_proxy()
        except OSError as exc:
            _LOGGER.warning("方太本地最小云启动失败: %s", exc)
            self._discovery_error = "cannot_start_discovery"
            await self._async_stop_discovery_proxy()
        except asyncio.CancelledError:
            await self._async_stop_discovery_proxy()
            raise

    async def _async_stop_discovery_proxy(self) -> None:
        """停止临时发现用本地云."""
        if self._discovery_proxy is None:
            return
        await self._discovery_proxy.async_stop()
        self._discovery_proxy = None

    def _handle_device_info(self, info: dict[str, str]) -> None:
        """接收本地云从烟机 HTTP 请求中提取的身份信息."""
        if CONF_DEVICE_ID in info:
            self._discovered[CONF_DEVICE_ID] = info[CONF_DEVICE_ID]
        if CONF_DEVICE_SERIAL in info:
            self._discovered[CONF_DEVICE_SERIAL] = info[CONF_DEVICE_SERIAL]

        if self._discovery_ready:
            if self._discovery_event is not None:
                self._discovery_event.set()
            self.async_update_progress(1.0)
        elif self._discovered:
            self.async_update_progress(0.5)

    async def _async_default_mqtt_host(self) -> str:
        """默认使用 HA 主机局域网 IP，适配同机 EMQX add-on."""
        return await network.async_get_source_ip(self.hass)

    @property
    def _discovery_ready(self) -> bool:
        """是否已拿到创建配置项所需的两个身份字段."""
        return bool(
            self._discovered.get(CONF_DEVICE_ID)
            and self._discovered.get(CONF_DEVICE_SERIAL)
        )
