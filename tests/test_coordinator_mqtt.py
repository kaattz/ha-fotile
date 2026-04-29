"""MQTT coordinator behavior tests."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


class FakeHass:
    def __init__(self) -> None:
        self.tasks = []

    def async_create_task(self, coro):
        import asyncio

        task = asyncio.create_task(coro)
        self.tasks.append(task)
        return task


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


@pytest.mark.asyncio
async def test_setup_retries_initial_status_queries_until_state_arrives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    device_class = load_coordinator_class()
    coordinator_module = sys.modules["custom_components.fotile.coordinator"]
    import homeassistant.components.mqtt as mqtt

    sleeps: list[int] = []
    published: list[tuple[str, str, int]] = []

    async def fast_sleep(delay: int) -> None:
        sleeps.append(delay)

    async def capture_publish(hass: Any, topic: str, payload: str, qos: int) -> None:
        published.append((topic, payload, qos))

    monkeypatch.setattr(coordinator_module, "sleep", fast_sleep)
    mqtt.async_publish = capture_publish

    hass = FakeHass()
    device = device_class(
        hass=hass,
        device_id="9d956a565f4727625e2f43ab6e0814b7",
        device_serial="1147191980",
        device_name="方太油烟机",
    )

    await device.async_setup()
    assert hass.tasks
    await hass.tasks[0]

    assert sleeps == [5, 10, 15]
    assert [topic for topic, _payload, _qos in published] == [
        "control/9d956a565f4727625e2f43ab6e0814b7/1147191980",
        "control/9d956a565f4727625e2f43ab6e0814b7/1147191980",
        "control/9d956a565f4727625e2f43ab6e0814b7/1147191980",
        "control/9d956a565f4727625e2f43ab6e0814b7/1147191980",
    ]


@pytest.mark.asyncio
async def test_teardown_cancels_initial_status_retry_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    device_class = load_coordinator_class()
    coordinator_module = sys.modules["custom_components.fotile.coordinator"]

    sleep_started = False

    async def blocked_sleep(delay: int) -> None:
        nonlocal sleep_started
        sleep_started = True
        import asyncio

        await asyncio.Event().wait()

    monkeypatch.setattr(coordinator_module, "sleep", blocked_sleep)

    hass = FakeHass()
    device = device_class(
        hass=hass,
        device_id="9d956a565f4727625e2f43ab6e0814b7",
        device_serial="1147191980",
        device_name="方太油烟机",
    )

    await device.async_setup()
    assert hass.tasks
    await asyncio.sleep(0)
    assert sleep_started

    await device.async_teardown()
    await asyncio.sleep(0)

    assert hass.tasks[0].cancelled()
