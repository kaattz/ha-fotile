"""MQTT coordinator behavior tests."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_coordinator_class() -> type:
    """Load coordinator.py without requiring Home Assistant to be installed."""
    package = types.ModuleType("custom_components.fotile")
    package.__path__ = [str(REPO_ROOT / "custom_components" / "fotile")]
    sys.modules["custom_components.fotile"] = package

    mqtt_module = types.ModuleType("homeassistant.components.mqtt")
    mqtt_module.ReceiveMessage = object

    async def fake_subscribe(*args: Any, **kwargs: Any) -> None:
        return None

    async def fake_publish(*args: Any, **kwargs: Any) -> None:
        return None

    mqtt_module.async_subscribe = fake_subscribe
    mqtt_module.async_publish = fake_publish

    homeassistant_module = types.ModuleType("homeassistant")
    components_module = types.ModuleType("homeassistant.components")
    components_module.mqtt = mqtt_module
    core_module = types.ModuleType("homeassistant.core")
    core_module.HomeAssistant = object
    core_module.callback = lambda func: func

    sys.modules["homeassistant"] = homeassistant_module
    sys.modules["homeassistant.components"] = components_module
    sys.modules["homeassistant.components.mqtt"] = mqtt_module
    sys.modules["homeassistant.core"] = core_module

    const_spec = importlib.util.spec_from_file_location(
        "custom_components.fotile.const",
        REPO_ROOT / "custom_components" / "fotile" / "const.py",
    )
    assert const_spec and const_spec.loader
    const_module = importlib.util.module_from_spec(const_spec)
    sys.modules["custom_components.fotile.const"] = const_module
    const_spec.loader.exec_module(const_module)

    coordinator_spec = importlib.util.spec_from_file_location(
        "custom_components.fotile.coordinator",
        REPO_ROOT / "custom_components" / "fotile" / "coordinator.py",
    )
    assert coordinator_spec and coordinator_spec.loader
    coordinator_module = importlib.util.module_from_spec(coordinator_spec)
    sys.modules["custom_components.fotile.coordinator"] = coordinator_module
    coordinator_spec.loader.exec_module(coordinator_module)
    return coordinator_module.FotileDevice


@pytest.mark.asyncio
async def test_query_all_status_publishes_null_command_to_control_topic() -> None:
    device_class = load_coordinator_class()
    import homeassistant.components.mqtt as mqtt

    published: list[tuple[str, str, int]] = []

    async def capture_publish(hass: Any, topic: str, payload: str, qos: int) -> None:
        published.append((topic, payload, qos))

    mqtt.async_publish = capture_publish

    device = device_class(
        hass=object(),
        device_id="9d956a565f4727625e2f43ab6e0814b7",
        device_serial="1147191980",
        device_name="方太油烟机",
    )

    await device.async_query_all_status()

    assert published == [
        (
            "control/9d956a565f4727625e2f43ab6e0814b7/1147191980",
            '{"updateAllStatus": null}',
            1,
        )
    ]
    assert json.loads(published[0][1]) == {"updateAllStatus": None}
