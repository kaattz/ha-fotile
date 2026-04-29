"""方太智慧厨房集成 - 本地最小云 HTTP 服务."""

from __future__ import annotations

import base64
import json
import logging
import time
from datetime import datetime
from typing import Any, Callable

from aiohttp import web

_LOGGER = logging.getLogger(__name__)

LOCAL_VENDOR_ID = "Fotile"
LOCAL_SCHEMA_VERSION = "V001"

ROUTE_TOPICS: list[dict[str, Any]] = [
    {
        "name": "service/{product_id}/{device_id}",
        "level": 1,
        "indentifier": "service",
        "isSubPub": 1,
    },
    {
        "name": "control/{product_id}/{device_id}",
        "level": 1,
        "indentifier": "control",
        "isSubPub": 1,
    },
    {
        "name": "sync/{product_id}/{device_id}",
        "level": 1,
        "indentifier": "sync",
        "isSubPub": 2,
    },
    {
        "name": "CustomEvent/{device_id}",
        "level": 1,
        "indentifier": "CustomEvent",
        "isSubPub": 1,
    },
    {
        "name": "reply/{product_id}/{device_id}",
        "level": 1,
        "indentifier": "reply",
        "isSubPub": 2,
    },
]

TSL_PRODUCT_RESPONSE: dict[str, Any] = {
    "AL": [
        {"n": "PowerSwitchAll", "c": {"o": 0, "l": 8, "b": 0}, "s": {"o": 0, "l": 8}},
        {"n": "WorkMode", "c": {"o": 8, "l": 8, "b": 1}, "s": {"o": 8, "l": 8}},
        {"n": "FanLevel", "c": {"o": 16, "l": 8, "b": 4}, "s": {"o": 16, "l": 8}},
        {"n": "AirFanLevel", "c": {"o": 24, "l": 8, "b": 11}, "s": {"o": 24, "l": 8}},
        {"n": "Light", "c": {"o": 32, "l": 8, "b": 2}, "s": {"o": 32, "l": 8}},
        {"n": "Ambientlight", "c": {"o": 40, "l": 8, "b": 8}, "s": {"o": 40, "l": 8}},
        {"n": "Delay", "s": {"o": 48, "l": 8}},
        {"n": "DelayTime", "c": {"o": 56, "l": 8, "b": 5}, "s": {"o": 56, "l": 8}},
        {"n": "GestureState", "c": {"o": 64, "l": 8, "b": 6}, "s": {"o": 64, "l": 8}},
        {"n": "SelfCleanRemindTime", "c": {"o": 72, "l": 8, "b": 10}, "s": {"o": 72, "l": 8}},
        {"n": "LockScreen", "c": {"o": 80, "l": 8, "b": 9}, "s": {"o": 80, "l": 8}},
        {"n": "AddWaterRemind", "s": {"o": 88, "l": 8}},
        {"n": "CleanRemind", "s": {"o": 96, "l": 8}},
        {"n": "EmptyOilCupRemind", "s": {"o": 104, "l": 8}},
        {"n": "RangeLinkageStove", "s": {"o": 176, "l": 8}},
        {"n": "AirStewardSensorWorkState", "s": {"o": 188, "l": 4}},
        {"n": "AirStewardAirQuality", "s": {"o": 184, "l": 4}},
        {
            "n": "ShedOilAfterMachineUsed",
            "c": {"o": 112, "l": 8, "b": 14},
            "s": {"o": 216, "l": 8},
        },
        {
            "n": "SingleOpenSingleInhale",
            "c": {"o": 88, "l": 8, "b": 12},
            "s": {"o": 192, "l": 8},
        },
        {"n": "UserDefinedLight", "c": {"o": 99, "l": 1, "b": 13}, "s": {"o": 203, "l": 1}},
        {
            "n": "UserDefinedFanGear",
            "c": {"o": 96, "l": 3, "b": 13},
            "s": {"o": 200, "l": 3},
        },
        {"n": "CtlUpDown", "c": {"o": 128, "l": 8, "b": 16}, "s": {"o": 232, "l": 8}},
        {
            "n": "UserDefinedUpDown",
            "c": {"o": 104, "l": 8, "b": 7},
            "s": {"o": 208, "l": 8},
        },
        {"n": "UpDownLock", "c": {"o": 136, "l": 8, "b": 17}, "s": {"o": 240, "l": 8}},
        {"n": "UpDownPosition", "s": {"o": 248, "l": 8}},
        {"n": "RunningTime", "s": {"o": 144, "l": 16}},
    ],
    "version": LOCAL_SCHEMA_VERSION,
    "dataType": 1,
    "uploadFilter": 1,
    "c": {"pB": {"o": 34, "l": 4}, "p": {"o": 38, "l": 20}},
    "s": {"p": {"o": 18, "l": 64}},
}


class FotileProxy:
    """本地实现烟机上线所需的最小 REST API."""

    def __init__(
        self,
        mqtt_host: str,
        device_id: str | None,
        port: int = 80,
        device_serial: str | None = None,
        mqtt_port: int = 1883,
        on_device_info: Callable[[dict[str, str]], None] | None = None,
    ) -> None:
        self._mqtt_host = mqtt_host
        self._mqtt_port = mqtt_port
        self._device_id = device_id or ""
        self._device_serial = device_serial or ""
        self._on_device_info = on_device_info
        self._port = port
        self._app = web.Application()
        self._runner: web.AppRunner | None = None
        self._setup_routes()

    def _setup_routes(self) -> None:
        self._app.router.add_route("*", "/{path:.*}", self._handle_request)

    async def _handle_request(self, request: web.Request) -> web.Response:
        """处理烟机 REST 请求，不访问官方云."""
        path = request.path
        method = request.method.upper()
        body = await request.read()

        _LOGGER.debug("本地云请求: %s %s", method, path)

        if method == "POST" and path == "/v5/time_sync/":
            return self._time_sync_response()
        if method == "POST" and path == "/v2/new_device_login":
            return self._device_login_response(body)
        if method == "POST" and path == "/iot-mqttManager/routeService":
            return self._route_service_response(body)
        if method == "POST" and path == "/v2/tsl/query/product":
            return self._tsl_query_product_response(body)

        self._log_unknown_request(method, path, request.headers, body)
        return self._json_response(
            {"error": "not_implemented", "method": method, "path": path},
            status=404,
        )

    def _time_sync_response(self) -> web.Response:
        now_ms = int(time.time() * 1000)
        now_seconds = now_ms // 1000
        payload = {
            "timestampString": datetime.fromtimestamp(now_seconds).strftime("%Y%m%d%H%M%S"),
            "timestampSeconds": now_seconds,
            "timestampMs": now_ms,
        }
        return self._json_response(payload, content_type="text/plain")

    def _device_login_response(self, body: bytes) -> web.Response:
        request_data = self._read_json_body(body)
        device_serial = str(request_data.get("deviceId") or self._device_serial)
        self._capture_device_serial(device_serial)
        now_ms = int(time.time() * 1000)
        payload = {
            "currentTimeStamp": now_ms,
            "deviceId": device_serial,
            "familyId": self._family_id(device_serial),
            "refreshToken": self._token("refresh", device_serial, now_ms),
            "refreshTokenTimeStamp": now_ms + 30 * 24 * 60 * 60 * 1000,
            "schemaVersion": LOCAL_SCHEMA_VERSION,
            "token": self._token("access", device_serial, now_ms),
            "tokenTimeStamp": now_ms + 24 * 60 * 60 * 1000,
        }
        return self._json_response(payload)

    def _route_service_response(self, body: bytes) -> web.Response:
        request_data = self._read_json_body(body)
        device_serial = str(
            request_data.get("deviceId") or self._device_serial or self._device_id or "0"
        )
        self._capture_device_serial(device_serial)
        payload = [
            {
                "ip": self._mqtt_host,
                "topics": ROUTE_TOPICS,
                "port": self._mqtt_port,
                "vendorId": LOCAL_VENDOR_ID,
                "clientId": f"Fotile_DEV_{device_serial}",
                "keepalived": 30,
            }
        ]
        return self._json_response(payload)

    def _tsl_query_product_response(self, body: bytes) -> web.Response:
        request_data = self._read_json_body(body)
        self._capture_device_id(request_data.get("productId"))
        return self._json_response(TSL_PRODUCT_RESPONSE)

    def _read_json_body(self, body: bytes) -> dict[str, Any]:
        if not body:
            return {}
        try:
            data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _json_response(
        self,
        payload: Any,
        status: int = 200,
        content_type: str = "application/json",
    ) -> web.Response:
        return web.Response(
            status=status,
            text=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            content_type=content_type,
        )

    def _log_unknown_request(
        self,
        method: str,
        path: str,
        headers: Any,
        body: bytes,
    ) -> None:
        body_text = body.decode("utf-8", errors="replace")[:500]
        header_names = sorted(headers.keys()) if hasattr(headers, "keys") else []
        _LOGGER.warning(
            "未实现的方太本地云接口: method=%s path=%s headers=%s body=%s",
            method,
            path,
            header_names,
            body_text,
        )

    def _token(self, kind: str, device_serial: str, timestamp_ms: int) -> str:
        raw = f"fotile-local:{kind}:{device_serial}:{timestamp_ms}".encode("utf-8")
        return base64.b64encode(raw).decode("ascii")

    def _family_id(self, device_serial: str) -> int:
        if device_serial.isdigit():
            return int(device_serial) % 1_000_000_000
        return 0

    def _capture_device_serial(self, device_serial: Any) -> None:
        if device_serial is None:
            return
        self._device_serial = str(device_serial)
        self._emit_device_info()

    def _capture_device_id(self, device_id: Any) -> None:
        if not device_id:
            return
        self._device_id = str(device_id)
        self._emit_device_info()

    def _emit_device_info(self) -> None:
        if self._on_device_info is None:
            return
        info: dict[str, str] = {}
        if self._device_id:
            info["device_id"] = self._device_id
        if self._device_serial:
            info["device_serial"] = self._device_serial
        if info:
            self._on_device_info(info)

    async def async_start(self) -> None:
        """启动 HTTP 服务."""
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self._port)
        await site.start()
        _LOGGER.info(
            "Fotile 本地最小云已启动: 0.0.0.0:%s (MQTT %s:%s)",
            self._port,
            self._mqtt_host,
            self._mqtt_port,
        )

    async def async_stop(self) -> None:
        """停止 HTTP 服务."""
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
            _LOGGER.info("Fotile 本地最小云已停止")
