# Lessons

- Home Assistant config flow menu labels for custom integrations should not rely only on translation files during HACS upgrade testing. Frontend translation cache can lag behind newly loaded Python code, so critical menu labels should be passed directly as a `menu_options` mapping.
- Any config flow that starts a temporary local server must implement `async_remove` and stop that server when the flow is closed; otherwise the next flow attempt can fail with `cannot_start_discovery` because the port is still occupied.
