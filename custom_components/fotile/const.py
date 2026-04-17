"""方太智慧厨房集成 - 常量定义."""

DOMAIN = "fotile"

# ── Config Entry 键名 ──────────────────────────────────────────────
CONF_DEVICE_ID = "device_id"
CONF_DEVICE_SERIAL = "device_serial"
CONF_MQTT_HOST = "mqtt_host"
CONF_PROXY_PORT = "proxy_port"
CONF_DEVICE_MQTT_HOST = "device_mqtt_host"
CONF_UPSTREAM_HOST = "upstream_host"
CONF_UPSTREAM_IP = "upstream_ip"

# ── 默认值 ────────────────────────────────────────────────────────
DEFAULT_PROXY_PORT = 80
DEFAULT_DEVICE_NAME = "方太油烟机"
DEFAULT_DEVICE_MQTT_HOST = ""  # 空 = 与 mqtt_host 相同
DEFAULT_UPSTREAM_HOST = "api.fotile.com"
DEFAULT_UPSTREAM_IP = "101.37.40.179"

# ── MQTT Topic 模板 ───────────────────────────────────────────────
# {device_id} = 32位hex产品标识, {device_serial} = 设备序列号
TOPIC_SYNC = "sync/{device_id}/#"
TOPIC_CONTROL = "control/{device_id}/{device_serial}"
TOPIC_SERVICE = "service/{device_id}/{device_serial}"
TOPIC_REPLY = "reply/{device_id}/#"

# ── Entity 平台列表 ──────────────────────────────────────────────
MQTT_QOS = 1

# Entity 平台列表
PLATFORMS: list[str] = ["fan", "light", "cover", "switch", "select", "number", "sensor", "button"]

# ── 设备属性键名 (MQTT Payload JSON keys) ────────────────────────
KEY_POWER = "PowerSwitchAll"
KEY_WORK_MODE = "WorkMode"
KEY_FAN_LEVEL = "FanLevel"
KEY_LIGHT = "Light"
KEY_CTL_UP_DOWN = "CtlUpDown"
KEY_UP_DOWN_POSITION = "UpDownPosition"
KEY_UP_DOWN_LOCK = "UpDownLock"
KEY_DELAY_TIME = "DelayTime"
KEY_AIR_QUALITY = "AirStewardAirQuality"
KEY_RUNNING_TIME = "RunningTime"
KEY_GESTURE_STATE = "GestureState"
KEY_SELF_CLEAN_REMIND = "SelfCleanRemind"
KEY_AIR_FAN_LEVEL = "AirFanLevel"
KEY_AMBIENT_LIGHT = "AmbientLight"
KEY_RANGE_LINKAGE_STOVE = "RangeLinkageStove"
KEY_AIR_STEWARD_SENSOR = "AirStewardSensorWorkState"
KEY_DELAY = "Delay"

# ── 属性取值常量 ─────────────────────────────────────────────────
# PowerSwitchAll
POWER_OFF = 1
POWER_ON = 2

# WorkMode
WORK_MODE_OFF = 0
WORK_MODE_MANUAL = 1
WORK_MODE_AUTO = 2

# FanLevel (仅 WorkMode=1 手动档时有效)
FAN_LEVEL_LOW = 2
FAN_LEVEL_HIGH = 3

# Light
LIGHT_OFF = 0
LIGHT_ON = 255

# CtlUpDown
CTL_STOP = 0
CTL_UP = 1
CTL_DOWN = 2

# UpDownLock
LOCK_OFF = 0
LOCK_ON = 1

# Fan preset mode 名称
PRESET_MODE_LOW = "low"
PRESET_MODE_HIGH = "high"
PRESET_MODE_AUTO = "auto"
