# 方太油烟机 Home Assistant 集成

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

将方太智能油烟机接入 Home Assistant，支持风机、照明、升降面板等完整控制。

## 工作原理

```
┌────────────┐   HTTP api.fotile.com:80   ┌────────────────────┐
│  油烟机     │ ─────────────────────────► │ HA 本地最小云       │
│ 192.168.x  │                            │ time/login/route/TSL│
└────────────┘                            └────────────────────┘
      │                                                      
      │  MQTT (port 1883)          ┌──────────────────┐
      └───────────────────────────►│  EMQX add-on     │◄──────── Home Assistant MQTT 集成
                                   │  允许烟机匿名连接 │
                                   │  HA_IP:1883      │
                                   └──────────────────┘
```

**核心思路**：
1. **本地最小云** — 拦截油烟机对 `api.fotile.com` 的 HTTP 请求，在本地直接实现 `time_sync`、`new_device_login`、`routeService`、`tsl/query/product`
2. **EMQX add-on 作为唯一 MQTT Broker** — 烟机需要匿名 MQTT，EMQX 更适合承接烟机连接
3. **HA 直接连接 EMQX** — Home Assistant 的 MQTT 集成直接配置到 EMQX，不需要 Mosquitto Bridge
4. **离线运行** — HA 控制烟机不再依赖方太官方 API；OpenWrt 负责 DNS 劫持和 HTTP DNAT，让烟机请求进入 HA

不建议继续用 Mosquitto 作为主 Broker：烟机大概率无法通过 Mosquitto 的认证要求。若坚持使用 Mosquitto，就需要额外部署 EMQX 接收烟机匿名连接，再配置 Bridge 同步到 HA Mosquitto，链路更长，排障也更麻烦。

## 前置条件

| 组件 | 说明 |
|------|------|
| Home Assistant | 2024.1+ (HAOS 推荐) |
| EMQX add-on | 推荐的唯一 MQTT Broker，允许烟机匿名连接 |
| OpenWrt 路由器 | 用于固定 DNS 劫持 `api.fotile.com`，并把烟机 HTTP 80 转发到 HA |

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

### 第一步：准备自动发现

不需要手工填写设备标识和设备序列号。添加集成后，烟机断电重启时会主动请求本地最小云，集成会自动从这些请求里提取：

| 字段 | 自动来源 |
|------|----------|
| 设备序列号 | `/v2/new_device_login` 请求体里的 `deviceId` |
| 设备标识 | `/v2/tsl/query/product` 请求体里的 `productId` |

### 第二步：配置 EMQX add-on

推荐在 HAOS 上安装 **EMQX add-on**，并让它作为唯一 MQTT Broker。烟机连接 EMQX，Home Assistant 的 MQTT 集成也连接 EMQX。

原因很简单：烟机需要匿名 MQTT；Mosquitto 默认不适合直接给烟机匿名连接。如果继续用 Mosquitto，就要额外用 EMQX 接烟机，再 Bridge 到 Mosquitto，配置会明显复杂。

| 客户端 | Broker 地址 |
|--------|-------------|
| 烟机 | `<HA_IP>:1883` |
| Home Assistant MQTT 集成 | EMQX add-on |
| Zigbee2MQTT | EMQX add-on |

HAOS 内部服务可以用 EMQX add-on 的内部地址；局域网设备用 HA 主机 IP。

Docker 环境也可以用 EMQX 容器：

```bash
docker run -d --name emqx \
  -p 1883:1883 \
  -p 18083:18083 \
  emqx/emqx:latest
```

EMQX 默认允许匿名连接。管理后台：`http://<EMQX_IP>:18083` (admin/public)

### 第三步：配置 HA MQTT 集成连接 EMQX

在 Home Assistant 中打开 MQTT 集成，把 Broker 改成 EMQX。

| 场景 | Broker 填写 |
|------|-------------|
| HAOS + EMQX add-on | `a0d7b954-emqx` 或 `homeassistant` |
| Docker / 外部 EMQX | EMQX 容器或主机 IP |
| 局域网设备连接 EMQX | HA 主机 IP |

如果 HA 上已有 Zigbee2MQTT，也要把 Zigbee2MQTT 的 MQTT 地址改到 EMQX。Zigbee 设备本身不用改。

### 第四步：配置 OpenWrt DNS + DNAT

在 OpenWrt 上把 `api.fotile.com` 固定解析到 HA，并把烟机访问的 TCP 80 强制转发到 HA。烟机会继续以为自己在访问官方域名，但实际访问的是 HA 本地最小云。

只做 DNS 不一定够：烟机可能缓存了官方 IP，抓包会看到它直接访问 `101.37.40.179:80`。DNAT 可以覆盖这种情况，不需要维护官方 IP。

在 OpenWrt 管理界面添加静态 DNS：

| 项 | 值 |
|----|----|
| 域名 | `api.fotile.com` |
| 地址 | `<HA_IP>` |

或者在 dnsmasq 自定义配置中加入：

```conf
address=/api.fotile.com/<HA_IP>
```

然后重启 dnsmasq，并断电重启烟机，让烟机重新解析域名。

再添加烟机专用 HTTP DNAT。以下示例里：

| 项 | 示例 |
|----|------|
| 烟机 IP | `192.168.166.200` |
| HA IP | `192.168.166.68` |

临时生效命令：

```bash
iptables -t nat -I PREROUTING 1 -i br-lan -s 192.168.166.200 -p tcp --dport 80 -j DNAT --to-destination 192.168.166.68:80
iptables -t nat -I POSTROUTING 1 -s 192.168.166.200 -d 192.168.166.68 -p tcp --dport 80 -j MASQUERADE
```

确认规则命中：

```bash
iptables -t nat -L PREROUTING -n -v --line-numbers | grep 192.168.166.200
iptables -t nat -L POSTROUTING -n -v --line-numbers | grep 192.168.166.68
```

持久化规则可以写入 OpenWrt 防火墙：

```bash
uci add firewall redirect
uci set firewall.@redirect[-1].name='fotile_http_to_ha'
uci set firewall.@redirect[-1].src='lan'
uci set firewall.@redirect[-1].src_ip='192.168.166.200'
uci set firewall.@redirect[-1].proto='tcp'
uci set firewall.@redirect[-1].src_dport='80'
uci set firewall.@redirect[-1].dest='lan'
uci set firewall.@redirect[-1].dest_ip='192.168.166.68'
uci set firewall.@redirect[-1].dest_port='80'
uci set firewall.@redirect[-1].target='DNAT'
uci commit firewall
/etc/init.d/firewall restart
```

如果之前反复测试过，先清掉重复的手工规则：

```bash
while iptables -t nat -D PREROUTING -s 192.168.166.200 -p tcp --dport 80 -j DNAT --to-destination 192.168.166.68:80 2>/dev/null; do :; done
while iptables -t nat -D POSTROUTING -s 192.168.166.200 -d 192.168.166.68 -p tcp --dport 80 -j MASQUERADE 2>/dev/null; do :; done
```

如果烟机和 EMQX 不在同一网段，才需要额外做 MQTT 路由或防火墙放行；正常同网段不需要 MQTT 劫持。

### 第五步：添加集成

1. HA → 设置 → 设备与服务 → 添加集成
2. 搜索 "Fotile"
3. 选择配置方式：

| 方式 | 说明 |
|------|------|
| 自动获取设备信息 | 推荐。集成临时启动本地最小云，从烟机启动请求里提取设备信息 |
| 手动填写设备信息 | 已经知道 `productId` 和 `deviceId` 时使用 |

自动获取时，先关闭油烟机电源，等待 10 秒后重新上电，并保持页面打开。抓到信息后点击提交，页面会回到配置表单，并自动填好设备标识和设备序列号。

最后确认配置：

| 字段 | 说明 | 示例值 |
|------|------|--------|
| **设备标识** | 烟机 `/v2/tsl/query/product` 请求里的 `productId` | `9d956a565f4727625e2f43ab6e0814b7` |
| **设备序列号** | 烟机 `/v2/new_device_login` 请求里的 `deviceId` | `1147191980` |
| **MQTT Broker 局域网 IP** | EMQX 地址，通常会自动填 HA 主机 IP | `192.168.166.68` |
| **MQTT Broker 端口** | EMQX MQTT 端口，默认自动填 `1883` | `1883` |
| **本地最小云 HTTP 端口** | 本地最小云监听端口 | `80` |

确认无误后提交，才会创建配置项。

> 烟机访问的是固定的 `api.fotile.com:80`。本地最小云默认必须监听 HA 主机的 80 端口，并且 HA 服务器上的 80 端口不能被其他服务占用。只有额外配置 OpenWrt DNAT，把烟机访问的 80 转发到 HA 的其他端口时，才可以把这里改成其他端口。

### 第六步：验证

重启油烟机（断电恢复），观察 HA 日志：

```
Fotile 本地最小云已启动: 0.0.0.0:80
本地云请求: POST /v5/time_sync/
本地云请求: POST /v2/new_device_login
本地云请求: POST /iot-mqttManager/routeService
本地云请求: POST /v2/tsl/query/product
sync 状态更新: {'PowerSwitchAll': 2, 'Light': 0, ...}
```

集成启动后会在第 0、5、15、30 秒自动查询状态。只要其中一次收到 `sync` 或 `reply`，实体就会从不可用变为可用。

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
| `control/{device_id}/{serial}` | HA → 设备 | 控制指令和状态查询 |
| `service/{device_id}/{serial}` | HA → 设备 | 设备订阅，当前集成不主动发布 |

## 网络拓扑示例

```
                    ┌─────────────────────────────────────────────────┐
                    │                  OpenWrt 路由器                   │
                    │                                                 │
                    │  DNS + DNAT:                                    │
                    │    api.fotile.com → HA_IP                       │
                    │    烟机 tcp/80 → HA_IP:80                       │
                    └─────────────────────────────────────────────────┘
                              │              │              │
               ┌──────────────┤              │              ├──────────────┐
               │              │              │              │              │
        ┌──────┴──────┐ ┌─────┴─────┐ ┌─────┴─────┐ ┌─────┴─────┐       │
        │  油烟机      │ │        HAOS / HA Server        │ │  其他设备   │       │
        │ .166.200    │ │        .166.68                  │ │           │       │
        │             │ │           │ │           │ │           │       │
        │ WiFi 模块   │ │  本地最小云 + EMQX add-on       │ │           │       │
        │             │ │  HA MQTT 集成直接连接 EMQX      │ │           │       │
        └─────────────┘ └─────────────────────────────────┘ └───────────┘       │
                                                                        │
                    ┌───────────────────────────────────────────────────┘
                    │  互联网
                    │  HA 控制烟机不依赖官方 API
                    └──────────────────────────────────────
```

## 故障排查

### 油烟机未连接

1. **检查 DNS 和 DNAT**：HA 日志中是否有 `本地云请求: POST /v5/time_sync/`
   - 没有 → 检查 OpenWrt 中 `api.fotile.com -> HA_IP` 是否生效，并确认烟机 TCP 80 DNAT 规则有计数
2. **检查 MQTT 连接**：EMQX add-on 管理后台是否有 `Fotile_DEV_*` 客户端
   - 没有 → 检查 routeService 返回的 IP 是否正确
3. **检查 HA MQTT 集成**：Home Assistant 是否已经连接 EMQX
   - 没有 → 在 MQTT 集成里把 Broker 改成 EMQX

### Mosquitto 认证问题

油烟机连接 Mosquitto 时显示 `not authorised` → 烟机无法满足 Mosquitto 的认证要求。建议改用 EMQX add-on 作为唯一 Broker；否则必须配置 EMQX 到 Mosquitto 的 Bridge。

### routeService 未出现

油烟机只发 `time_sync` 不发 `routeService` → 重点看 `/v2/new_device_login` 是否返回成功；本地最小云必须按顺序响应 `time_sync`、`new_device_login`、`routeService`、`tsl/query/product`。

## 开发相关

### 项目结构

```
custom_components/fotile/
├── __init__.py          # 入口：启动 proxy + coordinator
├── config_flow.py       # UI 配置流程
├── const.py             # 常量定义
├── coordinator.py       # MQTT 通信协调器
├── entity.py            # 基础实体类
├── proxy.py             # 本地最小云 HTTP 服务（核心）
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
