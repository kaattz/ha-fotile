"""方太智慧厨房集成 - UI 配置流程."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import network
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import callback

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


def _build_manual_schema(
    default_mqtt_host: str,
    default_device_id: str = "",
    default_device_serial: str = "",
    default_mqtt_port: int = DEFAULT_MQTT_PORT,
    default_proxy_port: int = DEFAULT_PROXY_PORT,
) -> vol.Schema:
    """构建手动确认表单，默认指向 HA 主机上的 EMQX add-on."""
    return vol.Schema(
        {
            vol.Required(CONF_MQTT_HOST, default=default_mqtt_host): str,
            vol.Required(CONF_MQTT_PORT, default=default_mqtt_port): int,
            vol.Optional(CONF_PROXY_PORT, default=default_proxy_port): int,
            vol.Required(CONF_DEVICE_ID, default=default_device_id): str,
            vol.Required(CONF_DEVICE_SERIAL, default=default_device_serial): str,
        }
    )


class FotileConfigFlow(ConfigFlow, domain=DOMAIN):
    """方太油烟机配置流程.

    收集信息:
    - mqtt_host:        MQTT Broker 局域网 IP (默认 HA 主机 IP)
    - mqtt_port:        MQTT Broker 端口 (默认 1883)
    - proxy_port:       本地最小云 HTTP 端口 (默认 80)
    - device_id:        产品标识 productId
    - device_serial:    设备序列号 deviceId
    """

    VERSION = 1

    def __init__(self) -> None:
        """初始化发现状态."""
        super().__init__()
        self._base_data: dict[str, Any] = {}
        self._discovered: dict[str, str] = {}
        self._discovery_timeout_task: asyncio.Task | None = None
        self._discovery_proxy: FotileProxy | None = None
        self._discovery_error: str | None = None

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """入口步骤：选择自动获取或手动填写."""
        return self.async_show_menu(
            step_id="user",
            menu_options={
                "discover": "自动获取设备信息",
                "manual": "手动填写设备信息",
            },
        )

    @callback
    def async_remove(self) -> None:
        """配置流关闭时释放临时本地云端口."""
        if self._discovery_proxy is not None:
            self.hass.async_create_task(self._async_stop_discovery_proxy())

    async def async_step_manual(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """确认配置并创建配置项."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mqtt_host = user_input[CONF_MQTT_HOST].strip()
            if not mqtt_host:
                errors[CONF_MQTT_HOST] = "invalid_mqtt_host"

            mqtt_port = user_input[CONF_MQTT_PORT]
            if mqtt_port < 1 or mqtt_port > 65535:
                errors[CONF_MQTT_PORT] = "invalid_port"

            port = user_input.get(CONF_PROXY_PORT, DEFAULT_PROXY_PORT)
            if port is None:
                port = DEFAULT_PROXY_PORT
            if port < 1 or port > 65535:
                errors[CONF_PROXY_PORT] = "invalid_port"

            device_id = user_input[CONF_DEVICE_ID].strip()
            if not device_id:
                errors[CONF_DEVICE_ID] = "required_device_id"

            device_serial = user_input[CONF_DEVICE_SERIAL].strip()
            if not device_serial:
                errors[CONF_DEVICE_SERIAL] = "required_device_serial"

            if not errors:
                await self._async_stop_discovery_proxy()
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Fotile {device_id[:8]}...",
                    data={
                        CONF_DEVICE_ID: device_id,
                        CONF_DEVICE_SERIAL: device_serial,
                        CONF_MQTT_HOST: mqtt_host,
                        CONF_MQTT_PORT: mqtt_port,
                        CONF_PROXY_PORT: port,
                    },
                )

        return self.async_show_form(
            step_id="manual",
            data_schema=await self._async_manual_schema(user_input),
            errors=errors,
        )

    async def async_step_discover(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """启动本地云，让用户断电上电后手动检查发现结果."""
        if self._discovery_ready:
            await self._async_stop_discovery_proxy()
            return await self.async_step_manual()

        await self._async_start_discovery_proxy()

        errors: dict[str, str] = {}
        if self._discovery_error is not None:
            errors["base"] = self._discovery_error
        elif user_input is not None:
            errors["base"] = self._discovery_error or "discovery_not_ready"

        return self.async_show_form(
            step_id="discover",
            data_schema=vol.Schema({}),
            errors=errors,
        )

    async def _async_manual_schema(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> vol.Schema:
        """按当前输入、已发现结果和默认值生成手动确认表单."""
        await self._async_ensure_base_data()
        values = {
            **self._base_data,
            CONF_DEVICE_ID: self._discovered.get(CONF_DEVICE_ID, ""),
            CONF_DEVICE_SERIAL: self._discovered.get(CONF_DEVICE_SERIAL, ""),
        }
        if user_input:
            values.update(user_input)

        return _build_manual_schema(
            default_mqtt_host=values[CONF_MQTT_HOST],
            default_mqtt_port=values[CONF_MQTT_PORT],
            default_proxy_port=values[CONF_PROXY_PORT],
            default_device_id=values[CONF_DEVICE_ID],
            default_device_serial=values[CONF_DEVICE_SERIAL],
        )

    async def _async_ensure_base_data(self) -> None:
        """填充网络默认值."""
        if self._base_data:
            return
        self._base_data = {
            CONF_MQTT_HOST: await self._async_default_mqtt_host(),
            CONF_MQTT_PORT: DEFAULT_MQTT_PORT,
            CONF_PROXY_PORT: DEFAULT_PROXY_PORT,
        }

    async def _async_start_discovery_proxy(self) -> None:
        """启动临时本地云，等待烟机请求时提取身份信息."""
        if self._discovery_proxy is not None or self._discovery_error is not None:
            return

        await self._async_ensure_base_data()
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
        except OSError as exc:
            _LOGGER.warning("方太本地最小云启动失败: %s", exc)
            self._discovery_proxy = None
            self._discovery_error = "cannot_start_discovery"
            return

        self._discovery_timeout_task = self.hass.async_create_task(
            self._async_discovery_timeout()
        )

    async def _async_discovery_timeout(self) -> None:
        """发现超时后停止临时本地云，避免用户关闭页面后长期占用端口."""
        try:
            await asyncio.sleep(DISCOVERY_TIMEOUT)
        except asyncio.CancelledError:
            raise

        if not self._discovery_ready:
            self._discovery_error = "discovery_timeout"
            await self._async_stop_discovery_proxy()

    async def _async_stop_discovery_proxy(self) -> None:
        """停止临时发现用本地云."""
        timeout_task = self._discovery_timeout_task
        if (
            timeout_task is not None
            and timeout_task is not asyncio.current_task()
            and not timeout_task.done()
        ):
            timeout_task.cancel()
        self._discovery_timeout_task = None

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
