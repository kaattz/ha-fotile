"""Config flow discovery tests."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


class DoneTask:
    def done(self) -> bool:
        return True

    def exception(self) -> None:
        return None


class FakeDiscoveryProxy:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    async def async_start(self) -> None:
        self.started = True

    async def async_stop(self) -> None:
        self.stopped = True


class FakeHass:
    def async_create_task(self, coro):
        return coro


def load_config_flow_module():
    package_name = "custom_components.fotile"
    package = types.ModuleType(package_name)
    package.__path__ = [str(REPO_ROOT / "custom_components" / "fotile")]
    sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
    sys.modules[package_name] = package

    class FakeConfigFlow:
        def __init_subclass__(cls, **kwargs: Any) -> None:
            return None

        async def async_set_unique_id(self, unique_id: str) -> None:
            self.unique_id = unique_id

        def _abort_if_unique_id_configured(self) -> None:
            return None

        def async_create_entry(self, title: str, data: dict[str, Any]) -> dict[str, Any]:
            return {"type": "create_entry", "title": title, "data": data}

        def async_abort(self, reason: str) -> dict[str, Any]:
            return {"type": "abort", "reason": reason}

        def async_show_form(self, **kwargs: Any) -> dict[str, Any]:
            return {"type": "form", **kwargs}

        def async_show_progress(self, **kwargs: Any) -> dict[str, Any]:
            return {"type": "progress", **kwargs}

        def async_show_progress_done(self, **kwargs: Any) -> dict[str, Any]:
            return {"type": "progress_done", **kwargs}

        def async_update_progress(self, progress: float) -> None:
            self.progress = progress

    config_entries_module = types.ModuleType("homeassistant.config_entries")
    config_entries_module.ConfigFlow = FakeConfigFlow
    config_entries_module.ConfigFlowResult = dict

    network_module = types.ModuleType("homeassistant.components.network")

    async def async_get_source_ip(hass: Any) -> str:
        return "192.168.166.68"

    network_module.async_get_source_ip = async_get_source_ip
    components_module = types.ModuleType("homeassistant.components")
    components_module.network = network_module

    homeassistant_module = types.ModuleType("homeassistant")
    homeassistant_module.config_entries = config_entries_module
    homeassistant_module.components = components_module
    sys.modules["homeassistant"] = homeassistant_module
    sys.modules["homeassistant.components"] = components_module
    sys.modules["homeassistant.components.network"] = network_module
    sys.modules["homeassistant.config_entries"] = config_entries_module

    class Marker:
        def __init__(self, schema: str, default: Any = None) -> None:
            self.schema = schema
            self.default = default

        def __hash__(self) -> int:
            return hash((self.schema, self.default, type(self)))

        def __eq__(self, other: object) -> bool:
            return (
                isinstance(other, Marker)
                and self.schema == other.schema
                and self.default == other.default
                and type(self) is type(other)
            )

    class Required(Marker):
        pass

    class Optional(Marker):
        pass

    class Schema:
        def __init__(self, schema: dict[Any, Any]) -> None:
            self.schema = schema

    voluptuous_module = types.ModuleType("voluptuous")
    voluptuous_module.Required = Required
    voluptuous_module.Optional = Optional
    voluptuous_module.Schema = Schema
    sys.modules["voluptuous"] = voluptuous_module

    for module_name in ("const", "proxy", "config_flow"):
        full_name = f"{package_name}.{module_name}"
        spec = importlib.util.spec_from_file_location(
            full_name,
            REPO_ROOT / "custom_components" / "fotile" / f"{module_name}.py",
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[full_name] = module
        spec.loader.exec_module(module)

    return sys.modules[f"{package_name}.config_flow"]


def schema_keys(schema) -> set[str]:
    return {key.schema for key in schema.schema}


def test_initial_config_form_only_requires_network_settings() -> None:
    module = load_config_flow_module()

    keys = schema_keys(module._build_user_schema("192.168.166.68"))

    assert "device_id" not in keys
    assert "device_serial" not in keys
    assert keys == {
        "mqtt_host",
        "mqtt_port",
        "proxy_port",
    }


def test_user_form_defaults_mqtt_to_ha_lan_ip_and_emqx_port() -> None:
    module = load_config_flow_module()
    flow = module.FotileConfigFlow()
    flow.hass = FakeHass()

    import asyncio

    result = asyncio.run(flow.async_step_user())

    schema = result["data_schema"].schema
    defaults = {key.schema: key.default for key in schema}
    assert defaults["mqtt_host"] == "192.168.166.68"
    assert defaults["mqtt_port"] == 1883


def test_discovery_finish_creates_entry_with_captured_ids() -> None:
    module = load_config_flow_module()
    flow = module.FotileConfigFlow()
    flow._base_data = {
        "mqtt_host": "192.168.166.68",
        "mqtt_port": 1883,
        "proxy_port": 80,
    }
    flow._discovered = {
        "device_id": "9d956a565f4727625e2f43ab6e0814b7",
        "device_serial": "1147191980",
    }
    flow._discovery_task = DoneTask()

    import asyncio

    result = asyncio.run(flow.async_step_finish())

    assert result["type"] == "create_entry"
    assert result["title"] == "Fotile 9d956a56..."
    assert result["data"] == {
        "device_id": "9d956a565f4727625e2f43ab6e0814b7",
        "device_serial": "1147191980",
        "mqtt_host": "192.168.166.68",
        "mqtt_port": 1883,
        "proxy_port": 80,
    }


def test_discovery_step_creates_entry_when_task_is_done() -> None:
    module = load_config_flow_module()
    flow = module.FotileConfigFlow()
    flow._base_data = {
        "mqtt_host": "192.168.166.68",
        "mqtt_port": 1883,
        "proxy_port": 80,
    }
    flow._discovered = {
        "device_id": "9d956a565f4727625e2f43ab6e0814b7",
        "device_serial": "1147191980",
    }
    flow._discovery_task = DoneTask()

    import asyncio

    result = asyncio.run(flow.async_step_discovery())

    assert result["type"] == "create_entry"
    assert result["data"]["device_id"] == "9d956a565f4727625e2f43ab6e0814b7"


def test_successful_discovery_keeps_proxy_until_finish_step() -> None:
    module = load_config_flow_module()
    flow = module.FotileConfigFlow()
    flow._base_data = {
        "mqtt_host": "192.168.166.68",
        "mqtt_port": 1883,
        "proxy_port": 80,
    }
    proxy = FakeDiscoveryProxy()
    module.FotileProxy = lambda **kwargs: proxy

    async def run_discovery() -> None:
        task = asyncio.create_task(flow._async_discover_device())
        await asyncio.sleep(0)
        flow._handle_device_info(
            {
                "device_id": "9d956a565f4727625e2f43ab6e0814b7",
                "device_serial": "1147191980",
            }
        )
        await task

    import asyncio

    asyncio.run(run_discovery())

    assert proxy.started
    assert not proxy.stopped
    assert flow._discovery_proxy is proxy
