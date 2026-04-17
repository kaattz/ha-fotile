"""方太智慧厨房集成 - HTTP 伪装服务器.

本地伪装 api.fotile.com，直接返回本地 MQTT Broker 信息，
使油烟机连接到本地 MQTT 而非方太云。
"""

from __future__ import annotations

import json
import logging

from aiohttp import web

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class FotileProxy:
    """伪装 api.fotile.com 的本地 HTTP 服务器."""

    def __init__(
        self,
        mqtt_host: str,
        device_id: str,
        port: int = 80,
    ) -> None:
        """初始化伪装服务器.

        Args:
            mqtt_host: 本地 MQTT Broker 的局域网 IP.
            device_id: 设备标识 (用于构造 topics 字段).
            port: 监听端口, 默认 80.
        """
        self._mqtt_host = mqtt_host
        self._device_id = device_id
        self._port = port
        self._app = web.Application()
        self._runner: web.AppRunner | None = None
        self._setup_routes()

    def _setup_routes(self) -> None:
        """注册路由."""
        self._app.router.add_post(
            "/iot-mqttManager/routeService",
            self._handle_route_service,
        )
        self._app.router.add_post(
            "/v5/time_sync/{tail:.*}",
            self._handle_time_sync,
        )
        # 兜底: 其他请求返回 200
        self._app.router.add_route("*", "/{path:.*}", self._handle_fallback)

    async def _handle_route_service(self, request: web.Request) -> web.Response:
        """处理 routeService — 返回本地 MQTT Broker 信息.

        油烟机通过此接口获取 MQTT 服务器地址。
        原始响应格式: [{"ip":"121.43.26.229","topics":[...]}]
        我们直接返回本地 MQTT 地址。
        """
        body = await request.read()
        _LOGGER.debug("routeService 请求体: %s", body.decode("utf-8", errors="replace"))

        response_data = [
            {
                "ip": self._mqtt_host,
                "topics": [self._device_id],
            }
        ]
        _LOGGER.info(
            "routeService → 返回本地 MQTT: ip=%s, device_id=%s",
            self._mqtt_host,
            self._device_id,
        )
        return web.Response(
            body=json.dumps(response_data),
            content_type="application/json",
        )

    async def _handle_time_sync(self, request: web.Request) -> web.Response:
        """处理时间同步请求 — 返回当前时间戳."""
        import time

        now = int(time.time())
        response_data = {
            "timestamp": now,
            "code": 0,
            "msg": "success",
        }
        _LOGGER.debug("time_sync → 返回时间戳: %s", now)
        return web.Response(
            body=json.dumps(response_data),
            content_type="application/json",
        )

    async def _handle_fallback(self, request: web.Request) -> web.Response:
        """兜底路由 — 记录并返回空 200."""
        _LOGGER.debug(
            "收到未处理请求: %s %s (来自 %s)",
            request.method,
            request.path,
            request.remote,
        )
        return web.Response(status=200, text="OK")

    async def async_start(self) -> None:
        """启动 HTTP 服务器."""
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self._port)
        await site.start()
        _LOGGER.info(
            "Fotile 伪装服务器已启动: 0.0.0.0:%s (MQTT→%s)",
            self._port,
            self._mqtt_host,
        )

    async def async_stop(self) -> None:
        """停止 HTTP 服务器."""
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
            _LOGGER.info("Fotile 伪装服务器已停止")
