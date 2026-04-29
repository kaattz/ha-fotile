from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest


def load_proxy_class():
    root = Path(__file__).resolve().parents[1]
    package_name = "custom_components.fotile"
    package = types.ModuleType(package_name)
    package.__path__ = [str(root / "custom_components" / "fotile")]
    sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
    sys.modules[package_name] = package

    for module_name in ("const", "proxy"):
        full_name = f"{package_name}.{module_name}"
        spec = importlib.util.spec_from_file_location(
            full_name,
            root / "custom_components" / "fotile" / f"{module_name}.py",
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[full_name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)

    return sys.modules[f"{package_name}.proxy"].FotileProxy


class FakeRequest:
    def __init__(
        self,
        path: str,
        body: dict | None = None,
        method: str = "POST",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.path = path
        self.method = method
        self.headers = headers or {}
        self.query_string = ""
        self._body = json.dumps(body or {}).encode("utf-8")

    async def read(self) -> bytes:
        return self._body


def response_json(response):
    return json.loads(response.body.decode("utf-8"))


@pytest.fixture
def proxy():
    FotileProxy = load_proxy_class()
    return FotileProxy(
        mqtt_host="192.168.166.68",
        device_id="9d956a565f4727625e2f43ab6e0814b7",
        device_serial="1147191980",
    )


@pytest.mark.asyncio
async def test_time_sync_returns_device_time_shape(proxy):
    response = await proxy._handle_request(FakeRequest("/v5/time_sync/"))
    data = response_json(response)

    assert response.status == 200
    assert data["timestampString"].isdigit()
    assert len(data["timestampString"]) == 14
    assert isinstance(data["timestampSeconds"], int)
    assert isinstance(data["timestampMs"], int)


@pytest.mark.asyncio
async def test_device_login_returns_local_tokens(proxy):
    request = FakeRequest(
        "/v2/new_device_login",
        {"deviceId": 1147191980, "timeStamp": "1777451945"},
    )
    response = await proxy._handle_request(request)
    data = response_json(response)

    assert response.status == 200
    assert data["deviceId"] == "1147191980"
    assert data["schemaVersion"] == "V001"
    assert data["token"]
    assert data["refreshToken"]
    assert isinstance(data["tokenTimeStamp"], int)


@pytest.mark.asyncio
async def test_route_service_returns_local_mqtt(proxy):
    response = await proxy._handle_request(
        FakeRequest(
            "/iot-mqttManager/routeService",
            {"deviceId": 1147191980, "clientType": 3},
        )
    )
    data = response_json(response)

    assert response.status == 200
    assert data[0]["ip"] == "192.168.166.68"
    assert data[0]["port"] == 1883
    assert data[0]["clientId"] == "Fotile_DEV_1147191980"
    assert data[0]["vendorId"] == "Fotile"
    assert {topic["indentifier"] for topic in data[0]["topics"]} >= {
        "service",
        "control",
        "sync",
        "reply",
    }


@pytest.mark.asyncio
async def test_tsl_query_returns_captured_product_fields(proxy):
    response = await proxy._handle_request(
        FakeRequest(
            "/v2/tsl/query/product",
            {"productId": "9d956a565f4727625e2f43ab6e0814b7", "condensedVersion": 1},
        )
    )
    data = response_json(response)

    assert response.status == 200
    assert data["version"] == "V001"
    field_names = {field["n"] for field in data["AL"]}
    assert {"PowerSwitchAll", "WorkMode", "FanLevel", "Light", "RunningTime"} <= field_names


@pytest.mark.asyncio
async def test_unknown_api_is_explicit_error(proxy):
    response = await proxy._handle_request(FakeRequest("/unknown/api"))
    data = response_json(response)

    assert response.status == 404
    assert data["error"] == "not_implemented"
    assert data["path"] == "/unknown/api"


@pytest.mark.asyncio
async def test_proxy_reports_discovered_device_identity():
    FotileProxy = load_proxy_class()
    discovered = []
    proxy = FotileProxy(
        mqtt_host="192.168.166.68",
        device_id=None,
        device_serial=None,
        on_device_info=discovered.append,
    )

    await proxy._handle_request(
        FakeRequest("/v2/new_device_login", {"deviceId": 1147191980})
    )
    await proxy._handle_request(
        FakeRequest(
            "/v2/tsl/query/product",
            {"productId": "9d956a565f4727625e2f43ab6e0814b7"},
        )
    )

    assert discovered[-1] == {
        "device_id": "9d956a565f4727625e2f43ab6e0814b7",
        "device_serial": "1147191980",
    }
