# Fotile Smart Kitchen for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/kaattz/ha-fotile)](https://github.com/kaattz/ha-fotile/releases)
[![License](https://img.shields.io/github/license/kaattz/ha-fotile)](LICENSE)

方太智慧厨房 Home Assistant 自定义集成，**无需云服务**，纯本地控制方太油烟机。

## 工作原理

```
┌─ 路由器 DNS ─────────────────────────────────┐
│  api.fotile.com  →  Home Assistant 局域网 IP  │
└───────────────────────────────────────────────┘

油烟机  ──HTTP POST──▶  HA:80 (FotileProxy)
                          │ 直接返回本地 MQTT Broker 地址
                          ▼
油烟机  ──MQTT──▶  Mosquitto (HA MQTT Broker)
                          │
                    HA 实体控制
```

1. **本地 HTTP 伪装服务器** — 伪装 `api.fotile.com`，当油烟机请求 MQTT 路由信息时，直接返回本地 MQTT Broker IP，**不再经过方太云**
2. **MQTT 通信** — 通过 HA 内置 MQTT 集成与油烟机实时收发消息
3. **实体映射** — 将 MQTT 消息映射为原生 HA 实体，可在 UI / 自动化 / 语音助手中使用

## 支持的功能

| 实体类型 | 名称 | 功能 |
|:------:|------|------|
| 🌀 Fan | 油烟机 | 风速控制：弱风 / 强风 / 自动 |
| 💡 Light | 照明灯 | 开 / 关 |
| ↕️ Cover | 升降面板 | 升 / 降 / 暂停，位置反馈 |
| 🔒 Switch | 升降锁定 | 锁定 / 解锁升降 |
| ⏱️ Number | 延时关机 | 0–30 分钟滑块 |
| 🔄 Button | 刷新状态 | 手动查询全部设备状态 |
| 📊 Sensor | 空气质量 | AirSteward 空气质量指数 |
| 📊 Sensor | 累计运行时间 | 设备运行总时长 |
| 📊 Sensor | 升降位置 | 当前面板高度 (%) |

## 前置条件

- **Home Assistant** 2024.1.0 或更高
- **MQTT 集成**已配置 (如 Mosquitto Broker Add-on)
- **DNS 劫持**: 路由器或 DNS 服务器将 `api.fotile.com` 解析到 HA 主机的局域网 IP
- 通过抓包获取以下设备信息：
  - **设备标识 (device_id)** — MQTT Topic 路径中的 32 位 hex 字符串
  - **设备序列号 (device_serial)** — Topic 后缀中的数字串

## 安装

### 方式一：HACS (推荐)

1. 打开 HACS → **集成** → 右上角 **⋮** → **自定义存储库**
2. 添加 `https://github.com/kaattz/ha-fotile`，类别选择 **Integration**
3. 搜索 **Fotile Smart Kitchen** 并安装
4. 重启 Home Assistant

### 方式二：手动安装

1. 下载本仓库 [最新 Release](https://github.com/kaattz/ha-fotile/releases)
2. 将 `custom_components/fotile` 目录复制到 HA 配置目录的 `custom_components/` 下
3. 重启 Home Assistant

## 配置

1. 进入 **设置** → **设备与服务** → **添加集成**
2. 搜索 **Fotile Smart Kitchen**
3. 填写配置项：

| 配置项 | 说明 | 示例 |
|-------|------|------|
| 设备标识 | MQTT Topic 中的 32 位 hex | `a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4` |
| 设备序列号 | Topic 后缀数字串 | `1234567890` |
| MQTT Broker IP | HA 主机的局域网 IP | `192.168.1.100` |
| HTTP 端口 | 伪装服务器端口 (默认 80) | `80` |

## MQTT Topic 结构

```
控制(下发):  control/{device_id}/{device_serial}    ← HA → 油烟机
状态(上报):  sync/{device_id}/{device_serial}       ← 油烟机 → HA
服务(查询):  service/{device_id}/{device_serial}    ← HA → 油烟机
回复(应答):  reply/{device_id}/...                  ← 油烟机 → HA
```

## 协议参考

<details>
<summary>点击展开 MQTT 指令对照表</summary>

| 操作 | Payload |
|------|---------|
| 开机 | `{"PowerSwitchAll":2}` |
| 关机 | `{"PowerSwitchAll":1,"WorkMode":0}` |
| 弱风 (手动) | `{"PowerSwitchAll":2,"WorkMode":1,"FanLevel":2}` |
| 强风 (手动) | `{"PowerSwitchAll":2,"WorkMode":1,"FanLevel":3}` |
| 自动挡 | `{"PowerSwitchAll":2,"WorkMode":2}` |
| 开灯 | `{"Light":255,"PowerSwitchAll":2}` |
| 关灯 | `{"Light":0,"PowerSwitchAll":2}` |
| 升 | `{"CtlUpDown":1}` |
| 降 | `{"CtlUpDown":2}` |
| 暂停升降 | `{"CtlUpDown":0}` |
| 锁定升降 | `{"UpDownLock":1}` |
| 解锁升降 | `{"UpDownLock":0}` |
| 延时关机 | `{"DelayTime":3}` |
| 刷新全部状态 | `{"updateAllStatus":"null"}` (发到 service topic) |

</details>

## 调试

如遇到问题，在 `configuration.yaml` 中启用调试日志：

```yaml
logger:
  logs:
    custom_components.fotile: debug
```

建议使用 [MQTT Explorer](https://mqtt-explorer.com/) 监控实际 MQTT 通信。

## License

[Apache-2.0](LICENSE)
