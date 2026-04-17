"""方太智慧厨房集成 - UI 配置流程."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_MQTT_HOST,
    CONF_DEVICE_SERIAL,
    CONF_MQTT_HOST,
    CONF_PROXY_PORT,
    CONF_UPSTREAM_HOST,
    CONF_UPSTREAM_IP,
    DEFAULT_DEVICE_MQTT_HOST,
    DEFAULT_PROXY_PORT,
    DEFAULT_UPSTREAM_HOST,
    DEFAULT_UPSTREAM_IP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_DEVICE_SERIAL): str,
        vol.Required(CONF_MQTT_HOST): str,
        vol.Optional(CONF_PROXY_PORT, default=DEFAULT_PROXY_PORT): int,
        vol.Optional(CONF_DEVICE_MQTT_HOST, default=DEFAULT_DEVICE_MQTT_HOST): str,
        vol.Optional(CONF_UPSTREAM_HOST, default=DEFAULT_UPSTREAM_HOST): str,
        vol.Optional(CONF_UPSTREAM_IP, default=DEFAULT_UPSTREAM_IP): str,
    }
)


class FotileConfigFlow(ConfigFlow, domain=DOMAIN):
    """方太油烟机配置流程.

    收集信息:
    - device_id:        设备标识 (32位hex, 来自抓包的 topic 路径)
    - device_serial:    设备序列号 (来自抓包的 topic 后缀)
    - mqtt_host:        MQTT Broker 局域网 IP (HA Mosquitto 地址)
    - proxy_port:       HTTP 伪装服务器端口 (默认 80)
    - device_mqtt_host: 设备端 MQTT Broker (如 EMQX, 允许匿名; 空=同 mqtt_host)
    - upstream_host:    上游 API 域名 (默认 api.fotile.com)
    - upstream_ip:      上游 API 真实 IP (绕过 DNS 回环)
    """

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """用户配置步骤."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # 校验 device_id 格式 (应为32位hex)
            device_id = user_input[CONF_DEVICE_ID].strip()
            if len(device_id) < 16:
                errors[CONF_DEVICE_ID] = "invalid_device_id"

            # 校验 MQTT host 非空
            mqtt_host = user_input[CONF_MQTT_HOST].strip()
            if not mqtt_host:
                errors[CONF_MQTT_HOST] = "invalid_mqtt_host"

            # 校验端口范围
            port = user_input[CONF_PROXY_PORT]
            if port < 1 or port > 65535:
                errors[CONF_PROXY_PORT] = "invalid_port"

            if not errors:
                # 防止重复配置同一设备
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Fotile {device_id[:8]}...",
                    data={
                        CONF_DEVICE_ID: device_id,
                        CONF_DEVICE_SERIAL: user_input[CONF_DEVICE_SERIAL].strip(),
                        CONF_MQTT_HOST: mqtt_host,
                        CONF_PROXY_PORT: port,
                        CONF_DEVICE_MQTT_HOST: user_input.get(CONF_DEVICE_MQTT_HOST, "").strip(),
                        CONF_UPSTREAM_HOST: user_input.get(CONF_UPSTREAM_HOST, DEFAULT_UPSTREAM_HOST).strip(),
                        CONF_UPSTREAM_IP: user_input.get(CONF_UPSTREAM_IP, DEFAULT_UPSTREAM_IP).strip(),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

