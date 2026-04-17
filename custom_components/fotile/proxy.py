"""方太智慧厨房集成 - HTTP 伪装服务器.

透传所有请求到 api.fotile.com，仅拦截 routeService 替换 MQTT 地址。
与原始 addon 逻辑一致: 真实代理 + 改写 MQTT IP。
"""

from __future__ import annotations

import json
import logging

from aiohttp import ClientSession, ClientTimeout, web

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# 真实方太 API 服务器 (直接使用 IP 避免 DNS 劫持回环)
UPSTREAM_HOST = "api.fotile.com"
UPSTREAM_IP = "101.37.40.179"
UPSTREAM_SCHEME = "http"
UPSTREAM_TIMEOUT = ClientTimeout(total=15, connect=5)


class FotileProxy:
    """透传代理 api.fotile.com，仅改写 routeService 中的 MQTT 地址."""

    def __init__(
        self,
        mqtt_host: str,
        device_id: str,
        port: int = 80,
    ) -> None:
        self._mqtt_host = mqtt_host
        self._device_id = device_id
        self._port = port
        self._app = web.Application()
        self._runner: web.AppRunner | None = None
        self._session: ClientSession | None = None
        self._setup_routes()

    def _setup_routes(self) -> None:
        """注册路由 — 所有请求都走代理."""
        self._app.router.add_route("*", "/{path:.*}", self._handle_proxy)

    async def _handle_proxy(self, request: web.Request) -> web.Response:
        """透传请求到真实 api.fotile.com，仅修改 routeService 响应."""
        path = request.path
        method = request.method

        # 读取请求体
        body = await request.read()

        # 构造上游 URL — 使用真实 IP 避免 DNS 回环
        upstream_url = f"{UPSTREAM_SCHEME}://{UPSTREAM_IP}{path}"

        # 复制请求头，修正 Host
        headers = {}
        for key, value in request.headers.items():
            lower = key.lower()
            if lower in ("host",):
                headers[key] = UPSTREAM_HOST
            elif lower in ("transfer-encoding", "content-length"):
                continue  # 让 aiohttp 自动处理
            else:
                headers[key] = value

        _LOGGER.debug("代理请求: %s %s → %s", method, path, upstream_url)

        try:
            if self._session is None or self._session.closed:
                self._session = ClientSession(timeout=UPSTREAM_TIMEOUT)

            async with self._session.request(
                method,
                upstream_url,
                headers=headers,
                data=body,
                ssl=False,
            ) as upstream_resp:
                resp_body = await upstream_resp.read()

                # 拦截 routeService: 替换 MQTT IP
                if path == "/iot-mqttManager/routeService" and method == "POST":
                    resp_body = self._rewrite_mqtt_ip(resp_body)

                # 记录关键接口的响应体 (用于调试)
                if "device/access" in path or "routeService" in path:
                    _LOGGER.info(
                        "关键接口响应: %s → %s",
                        path,
                        resp_body.decode("utf-8", errors="replace")[:500],
                    )

                # 复制上游响应头
                resp_headers = {}
                for key, value in upstream_resp.headers.items():
                    lower = key.lower()
                    if lower not in (
                        "transfer-encoding",
                        "content-encoding",
                        "content-length",
                    ):
                        resp_headers[key] = value

                _LOGGER.debug(
                    "代理响应: %s %s → %s (%d bytes)",
                    method,
                    path,
                    upstream_resp.status,
                    len(resp_body),
                )

                return web.Response(
                    status=upstream_resp.status,
                    headers=resp_headers,
                    body=resp_body,
                )

        except Exception as exc:
            _LOGGER.warning("代理请求失败: %s %s → %s", method, path, exc)
            # 降级: routeService 直接返回本地信息
            if path == "/iot-mqttManager/routeService" and method == "POST":
                return self._fallback_route_service()
            return web.Response(status=200, text="OK")

    def _rewrite_mqtt_ip(self, content: bytes) -> bytes:
        """改写 routeService 响应中的 MQTT IP."""
        try:
            data = json.loads(content.decode("utf-8"))
            if isinstance(data, list) and len(data) > 0 and "ip" in data[0]:
                old_ip = data[0]["ip"]
                data[0]["ip"] = self._mqtt_host
                _LOGGER.info(
                    "routeService → MQTT IP 改写: %s → %s",
                    old_ip,
                    self._mqtt_host,
                )
            return json.dumps(data).encode("utf-8")
        except (json.JSONDecodeError, KeyError, IndexError, UnicodeDecodeError):
            _LOGGER.warning("routeService 响应解析失败，返回原始内容")
            return content

    def _fallback_route_service(self) -> web.Response:
        """降级: 直接返回本地 MQTT 信息."""
        response_data = [
            {
                "ip": self._mqtt_host,
                "topics": [self._device_id],
            }
        ]
        _LOGGER.info(
            "routeService (降级模式) → 返回本地 MQTT: ip=%s",
            self._mqtt_host,
        )
        return web.Response(
            body=json.dumps(response_data),
            content_type="application/json",
        )

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
        if self._session and not self._session.closed:
            await self._session.close()
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
            _LOGGER.info("Fotile 伪装服务器已停止")
