"""Config flow discovery tests."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


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
        return asyncio.create_task(coro)


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

        def async_show_menu(self, **kwargs: Any) -> dict[str, Any]:
            return {"type": "menu", **kwargs}

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


def schema_defaults(schema) -> dict[str, Any]:
    return {key.schema: key.default for key in schema.schema}


def test_initial_step_offers_auto_discovery_or_manual_entry() -> None:
    module = load_config_flow_module()
    flow = module.FotileConfigFlow()

    result = asyncio.run(flow.async_step_user())

    assert result["type"] == "menu"
    assert result["menu_options"] == ["discover", "manual"]


def test_manual_config_form_includes_network_and_device_fields() -> None:
    module = load_config_flow_module()
    flow = module.FotileConfigFlow()
    flow.hass = FakeHass()

    result = asyncio.run(flow.async_step_manual())

    keys = schema_keys(result["data_schema"])
    assert result["type"] == "form"
    assert result["step_id"] == "manual"
    assert keys == {
        "mqtt_host",
        "mqtt_port",
        "proxy_port",
        "device_id",
        "device_serial",
    }


def test_manual_form_defaults_to_ha_lan_ip_emqx_port_and_discovered_ids() -> None:
    module = load_config_flow_module()
    flow = module.FotileConfigFlow()
    flow.hass = FakeHass()
    flow._discovered = {
        "device_id": "9d956a565f4727625e2f43ab6e0814b7",
        "device_serial": "1147191980",
    }

    result = asyncio.run(flow.async_step_manual())

    defaults = schema_defaults(result["data_schema"])
    assert defaults["mqtt_host"] == "192.168.166.68"
    assert defaults["mqtt_port"] == 1883
    assert defaults["device_id"] == "9d956a565f4727625e2f43ab6e0814b7"
    assert defaults["device_serial"] == "1147191980"


def test_manual_submit_creates_entry_with_device_ids() -> None:
    module = load_config_flow_module()
    flow = module.FotileConfigFlow()

    result = asyncio.run(
        flow.async_step_manual(
            {
                "mqtt_host": "192.168.166.68",
                "mqtt_port": 1883,
                "proxy_port": 80,
                "device_id": "9d956a565f4727625e2f43ab6e0814b7",
                "device_serial": "1147191980",
            }
        )
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "Fotile 9d956a56..."
    assert result["data"] == {
        "device_id": "9d956a565f4727625e2f43ab6e0814b7",
        "device_serial": "1147191980",
        "mqtt_host": "192.168.166.68",
        "mqtt_port": 1883,
        "proxy_port": 80,
    }


def test_manual_submit_uses_default_proxy_port_when_omitted() -> None:
    module = load_config_flow_module()
    flow = module.FotileConfigFlow()

    result = asyncio.run(
        flow.async_step_manual(
            {
                "mqtt_host": "192.168.166.68",
                "mqtt_port": 1883,
                "device_id": "9d956a565f4727625e2f43ab6e0814b7",
                "device_serial": "1147191980",
            }
        )
    )

    assert result["type"] == "create_entry"
    assert result["data"]["proxy_port"] == 80


def test_auto_discovery_step_starts_local_cloud_and_shows_power_cycle_prompt() -> None:
    module = load_config_flow_module()
    flow = module.FotileConfigFlow()
    flow.hass = FakeHass()
    proxy = FakeDiscoveryProxy()
    module.FotileProxy = lambda **kwargs: proxy

    result = asyncio.run(flow.async_step_discover())

    assert result["type"] == "form"
    assert result["step_id"] == "discover"
    assert proxy.started
    assert not proxy.stopped


def test_auto_discovery_success_returns_manual_form_with_captured_defaults() -> None:
    module = load_config_flow_module()
    flow = module.FotileConfigFlow()
    flow.hass = FakeHass()
    proxy = FakeDiscoveryProxy()
    flow._discovery_proxy = proxy
    flow._discovered = {
        "device_id": "9d956a565f4727625e2f43ab6e0814b7",
        "device_serial": "1147191980",
    }

    result = asyncio.run(flow.async_step_discover({}))

    defaults = schema_defaults(result["data_schema"])
    assert result["type"] == "form"
    assert result["step_id"] == "manual"
    assert proxy.stopped
    assert defaults["device_id"] == "9d956a565f4727625e2f43ab6e0814b7"
    assert defaults["device_serial"] == "1147191980"
