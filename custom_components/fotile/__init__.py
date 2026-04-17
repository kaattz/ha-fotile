"""方太智慧厨房集成 - 入口.

启动流程:
1. 创建 FotileProxy (HTTP 伪装服务器)
2. 创建 FotileDevice (MQTT 通信协调器)
3. 注册实体平台 (fan, light, cover, switch, number, sensor)
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_SERIAL,
    CONF_MQTT_HOST,
    CONF_PROXY_PORT,
    DEFAULT_DEVICE_NAME,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import FotileDevice
from .proxy import FotileProxy

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """配置入口 — 启动伪装服务器和 MQTT 通信."""
    device_id = entry.data[CONF_DEVICE_ID]
    device_serial = entry.data[CONF_DEVICE_SERIAL]
    mqtt_host = entry.data[CONF_MQTT_HOST]
    proxy_port = entry.data[CONF_PROXY_PORT]

    # 1. 启动 HTTP 伪装服务器
    proxy = FotileProxy(
        mqtt_host=mqtt_host,
        device_id=device_id,
        port=proxy_port,
        device_mqtt_host="192.168.166.50",  # EMQX (允许匿名连接)
    )
    await proxy.async_start()

    # 2. 启动 MQTT 通信协调器
    device = FotileDevice(
        hass=hass,
        device_id=device_id,
        device_serial=device_serial,
        device_name=DEFAULT_DEVICE_NAME,
    )
    await device.async_setup()

    # 3. 存储引用
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "proxy": proxy,
        "device": device,
    }

    # 4. 注册实体平台
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info(
        "Fotile 集成已启动: device_id=%s, proxy_port=%s, mqtt=%s",
        device_id,
        proxy_port,
        mqtt_host,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载配置入口 — 停止所有服务."""
    data = hass.data[DOMAIN].get(entry.entry_id)
    if not data:
        return True

    # 停止 MQTT 通信
    device: FotileDevice = data["device"]
    await device.async_teardown()

    # 停止 HTTP 伪装服务器
    proxy: FotileProxy = data["proxy"]
    await proxy.async_stop()

    # 卸载实体平台
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    _LOGGER.info("Fotile 集成已卸载")
    return unload_ok
