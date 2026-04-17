# 方太油烟机 Home Assistant 集成

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

将方太智能油烟机接入 Home Assistant，支持风机、照明、升降面板等完整控制。

## 工作原理

```
┌────────────┐   HTTP (port 80)    ┌──────────────────┐   HTTP    ┌──────────────────┐
│  油烟机     │ ──────────────────► │  HA Proxy        │ ────────► │ api.fotile.com   │
│ 192.168.x  │                     │  (透传+改写MQTT) │ ◄──────── │ 101.37.40.179    │
└────────────┘                     └──────────────────┘           └──────────────────┘
      │                                                      
      │  MQTT (port 1883)          ┌──────────────────┐   Bridge  ┌──────────────────┐
      └───────────────────────────►│  EMQX            │ ────────► │  Mosquitto (HA)  │
                                   │  (匿名连接)      │ ◄──────── │  (认证连接)       │
                                   │  192.168.x.x     │           │  172.30.x.x      │
                                   └──────────────────┘           └──────────────────┘
```

**核心思路**：
1. **HTTP 透传代理** — 拦截油烟机对 `api.fotile.com` 的 HTTP 请求，透传给真实服务器，仅将 `routeService` 和 `device/access` 接口返回的 MQTT 地址替换为本地 Broker
2. **MQTT 匿名接入** — 油烟机不支持 MQTT 认证，需要一个允许匿名的 MQTT Broker（如 EMQX）作为中转
3. **Bridge 转发** — Mosquitto Bridge 在 EMQX 和 HA Mosquitto 之间同步消息

## 前置条件

| 组件 | 说明 |
|------|------|
| Home Assistant | 2024.1+ (HAOS 推荐) |
| Mosquitto Add-on | HA 官方 MQTT Broker |
| EMQX (可选) | 同局域网运行的 MQTT Broker，允许匿名连接 |
| OpenWrt 路由器 | 用于 iptables 流量劫持（也可用其他支持 DNAT 的路由器） |

## 安装

### 方式 1: HACS (推荐)

1. HACS → 集成 → 自定义存储库
2. 添加 `https://github.com/kaattz/ha-fotile`
3. 搜索 "Fotile" → 安装
4. 重启 Home Assistant

### 方式 2: 手动安装

```bash
cd /config/custom_components
git clone https://github.com/kaattz/ha-fotile.git fotile
# 或手动下载 zip 解压到 /config/custom_components/fotile/
ha core restart
```

## 配置步骤

### 第一步：获取设备信息

你需要从 MQTT 抓包中获取以下信息：

| 参数 | 说明 | 示例 |
|------|------|------|
| `device_id` | 32位 hex 产品标识 | `a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4` |
| `device_serial` | 设备序列号 | `1234567890` |

**获取方式**：用 MQTT Explorer 连接 EMQX，观察油烟机发布的 topic：
```
sync/a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4/1234567890
      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^^^
      device_id                        device_serial
```

### 第二步：配置 EMQX (匿名 MQTT Broker)

油烟机不支持 MQTT 认证，需要一个允许匿名的 Broker。

**使用 Docker 快速部署 EMQX：**

```bash
docker run -d --name emqx \
  -p 1883:1883 \
  -p 18083:18083 \
  emqx/emqx:latest
```

EMQX 默认允许匿名连接。管理后台：`http://<EMQX_IP>:18083` (admin/public)

### 第三步：配置 Mosquitto Bridge

在 HA 的 Mosquitto Add-on 中启用自定义配置：

1. Add-on 配置中设置 `customize.active: true`
2. 创建 `/share/mosquitto/bridge_emqx.conf`：

```conf
# Bridge: HA Mosquitto ←→ EMQX
connection emqx_fotile
address <EMQX_IP>:1883
clientid mosqbridge_to_emqx

cleansession true
try_private false
start_type automatic
notifications false
keepalive_interval 30
bridge_protocol_version mqttv311

# 替换为你的 device_id 和 device_serial
# 设备上报 (EMQX → Mosquitto):
topic sync/<device_id>/<device_serial> in 1
topic reply/<device_id>/<device_serial> in 1
topic CustomEvent/<device_serial> in 1

# HA 下发 (Mosquitto → EMQX):
topic service/<device_id>/<device_serial> out 1
topic control/<device_id>/<device_serial> out 1
```

重启 Mosquitto Add-on。

### 第四步：配置 OpenWrt 流量劫持

在 OpenWrt 路由器上添加 iptables 规则，将油烟机的 HTTP 和 MQTT 流量重定向到本地：

```bash
# 获取上游 API 真实 IP（可能会变，需确认）
nslookup api.fotile.com
# 假设为 101.37.40.179

# === HTTP 劫持 (油烟机 → HA Proxy) ===
iptables -t nat -A PREROUTING -s <油烟机IP> -p tcp --dport 80 -j DNAT --to-destination <HA_IP>:80
iptables -t nat -A POSTROUTING -s <油烟机IP> -d <HA_IP> -p tcp --dport 80 -j MASQUERADE

# === MQTT 劫持 (油烟机 → EMQX) ===
# 仅在 EMQX 与油烟机不在同一子网时需要
# 如果 EMQX 与油烟机在同一子网，proxy 会直接返回 EMQX IP，无需此规则
iptables -t nat -A PREROUTING -s <油烟机IP> -p tcp --dport 1883 -j DNAT --to-destination <EMQX_IP>:1883
iptables -t nat -A POSTROUTING -s <油烟机IP> -d <EMQX_IP> -p tcp --dport 1883 -j MASQUERADE
```

**持久化规则**（防止路由器重启丢失）：

在 OpenWrt 管理界面 → 网络 → 防火墙 → 自定义规则 中添加以上命令。

### 第五步：添加集成

1. HA → 设置 → 设备与服务 → 添加集成
2. 搜索 "Fotile"
3. 填写配置：

| 字段 | 说明 | 示例值 |
|------|------|--------|
| **设备标识** | 32位 hex product ID | `a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4` |
| **设备序列号** | 设备 serial | `1234567890` |
| **MQTT Broker 局域网 IP** | HA Mosquitto 地址 | `192.168.166.68` |
| **HTTP 伪装服务器端口** | Proxy 监听端口 | `80` |
| **设备端 MQTT Broker** | EMQX 地址（留空=同上） | `192.168.166.50` |
| **上游 API 域名** | 方太云 API 域名 | `api.fotile.com` |
| **上游 API 真实 IP** | 绕过 DNS 回环 | `101.37.40.179` |

> **为什么需要"上游 API 真实 IP"？**
> HA 自身的 DNS 可能会将 `api.fotile.com` 解析到本机（因为 DNS 劫持），导致代理回环。直接填真实 IP 可绕过此问题。

### 第六步：验证

重启油烟机（断电恢复），观察 HA 日志：

```
✅ time_sync → 返回时间戳
✅ new_device_login → 设备登录
✅ routeService → MQTT IP 改写: 47.x.x.x → 192.168.166.50
✅ sync 状态更新: {'PowerSwitchAll': 2, 'Light': 0, ...}
```

## 支持的实体

| 实体类型 | 名称 | 功能 |
|----------|------|------|
| `fan` | 油烟机 | 开关、风速模式 (弱风/强风/自动) |
| `light` | 照明灯 | 开/关 |
| `cover` | 升降面板 | 上升/下降/停止 |
| `switch` | 升降锁定 | 锁定/解锁升降功能 |
| `select` | 风量档位 | 弱风/强风/自动 |
| `number` | 延时关机 | 设置延时时间 (分钟) |
| `sensor` | 空气质量 | 空气质量传感器 |
| `sensor` | 累计运行时间 | 设备运行时长 |
| `sensor` | 升降位置 | 当前升降位置 |
| `button` | 刷新状态 | 手动查询设备全部状态 |

## MQTT Topic 格式

| Topic | 方向 | 说明 |
|-------|------|------|
| `sync/{device_id}/{serial}` | 设备 → HA | 设备状态上报 |
| `reply/{device_id}/{serial}` | 设备 → HA | 指令执行回复 |
| `control/{device_id}/{serial}` | HA → 设备 | 控制指令下发 |
| `service/{device_id}/{serial}` | HA → 设备 | 查询指令下发 |

## 网络拓扑示例

```
                    ┌─────────────────────────────────────────────────┐
                    │                  OpenWrt 路由器                   │
                    │                                                 │
                    │  iptables DNAT:                                  │
                    │    油烟机:80  → HA:80     (HTTP proxy)           │
                    │    油烟机:1883 → EMQX:1883 (MQTT, 可选)          │
                    └─────────────────────────────────────────────────┘
                              │              │              │
               ┌──────────────┤              │              ├──────────────┐
               │              │              │              │              │
        ┌──────┴──────┐ ┌─────┴─────┐ ┌─────┴─────┐ ┌─────┴─────┐       │
        │  油烟机      │ │   HA      │ │   EMQX    │ │  其他设备   │       │
        │ .166.200    │ │  .166.68  │ │  .166.50  │ │           │       │
        │             │ │           │ │           │ │           │       │
        │ WiFi 模块   │ │ Mosquitto │ │ 匿名MQTT  │ │           │       │
        │             │ │ Proxy     │ │           │ │           │       │
        │             │ │ 集成      │ │           │ │           │       │
        └─────────────┘ └───────────┘ └───────────┘ └───────────┘       │
                                           │                            │
                                    Mosquitto Bridge                    │
                                    (sync/reply ← EMQX)                │
                                    (service/control → EMQX)            │
                                                                        │
                    ┌───────────────────────────────────────────────────┘
                    │  互联网
                    │  api.fotile.com (101.37.40.179)
                    └──────────────────────────────────────
```

## 故障排查

### 油烟机未连接

1. **检查 HTTP 劫持**：HA 日志中是否有 `代理请求: POST /v5/time_sync/`
   - 没有 → 检查 iptables HTTP 规则
2. **检查 MQTT 连接**：EMQX 管理后台是否有 `Fotile_DEV_*` 客户端
   - 没有 → 检查 routeService 返回的 IP 是否正确
3. **检查 Bridge**：Mosquitto 日志是否有 `Bridge connection emqx_fotile established`
   - 没有 → 检查 `bridge_emqx.conf` 配置

### Mosquitto 认证问题

油烟机连接 Mosquitto 时显示 `not authorised` → 油烟机不支持 MQTT 认证，必须通过 EMQX（匿名 Broker）中转。

### DNS 回环

代理日志显示 `Cannot connect to host api.fotile.com:443 ssl:False [Timeout while contacting DNS servers]` → 填写 **上游 API 真实 IP** 字段，绕过 DNS。

### routeService 未被拦截

油烟机只发 `time_sync` 不发 `routeService` → 代理原先未正确响应 `time_sync`，请更新到最新版本（透传模式）。

## 开发相关

### 项目结构

```
custom_components/fotile/
├── __init__.py          # 入口：启动 proxy + coordinator
├── config_flow.py       # UI 配置流程
├── const.py             # 常量定义
├── coordinator.py       # MQTT 通信协调器
├── entity.py            # 基础实体类
├── proxy.py             # HTTP 透传代理（核心）
├── fan.py               # 风机实体
├── light.py             # 照明实体
├── cover.py             # 升降面板实体
├── switch.py            # 升降锁定开关
├── select.py            # 风量档位选择
├── number.py            # 延时关机设置
├── sensor.py            # 传感器实体
├── button.py            # 手动刷新按钮
├── manifest.json        # 集成清单
├── strings.json         # 翻译（主）
└── translations/
    ├── en.json           # 英文翻译
    └── zh-Hans.json      # 简体中文翻译
```

## License

MIT
