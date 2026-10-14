# 控客 Home Assistant 集成

通过固定主机公钥的 SSH 隧道，将控客主机管理的空调、地暖和新风接入 Home Assistant。社区项目，与控客官方无隶属关系。

## 兼容范围

仅验证过 **KK-CC-G12W / Home Assistant Core 2026.9.4** 环境；固件版本未记录。其他型号、固件或数据库结构尚未验证，不承诺兼容全部控客产品。元数据以 HA 2026.9.0 为最低安装版本，实际验证版本为 2026.9.4。

| 设备 | HA 类型 | 功能 |
| --- | --- | --- |
| 空调室内机 | `climate` | 开关、自动/制冷/制热/除湿/送风、自动/低/中/高风速、16–32°C 设定温度（步长 1°C） |
| 地暖通道 | `climate` | 开关、制热、5–45°C 设定温度（步长 0.5°C） |
| 新风设备 | `fan` | 开关、低/中/高三档风速（HA 百分比约 33/67/100） |

仅创建原厂已配置的设备，离线设备保留但不可控制。支持范围以具体设备原厂能力为准；设置温度不代表室温会立即变化。新风控制已在验证环境生效，未进行物理升降温测试。

## 工作方式与前提

- HA 能直接通过网络访问控客主机的 SSH 端口；本集成不内置跳板机、远程组网或云端账号功能。
- 你拥有该主机管理权限、SSH 用户名和密码，并能够独立核对 SSH 主机公钥。
- 原厂服务运行正常，SSH 账号可以读取原厂 SQLite 数据并建立 `direct-tcpip` 转发。
- 集成使用 `paramiko==3.5.1`；HA 首次加载需要能安装 Python 依赖。

状态通过原厂 SQLite 只读查询采集，默认每 30 秒轮询。控制通过 SSH 转发至主机回环端口 `127.0.0.1:5000`，调用原厂服务并重新读取状态；不直接修改数据库，不开放原厂控制端口到外网。

原厂服务路径、数据库表结构和协议具有型号依赖。协议中的 `local/local` 是原厂回环服务固定登录字段，与用户填写的 SSH 凭据不同。SSH 凭据保存在 HA 配置项中，备份也可能包含凭据，请按 HA 凭据管理方式保护备份。

## 安装

### 手动安装

1. 从 [v0.1.0 发布页](https://github.com/YyyQq-C/home-assistant-konke/releases/tag/v0.1.0) 下载 `home-assistant-konke-v0.1.0.zip`，解压到 HA 配置目录。该目录通常包含 `configuration.yaml`。
2. 确认安装后的路径是 `custom_components/konke_local/manifest.json`，避免多套一层仓库目录。
3. 重启 Home Assistant。
4. 打开「设置 → 设备与服务 → 添加集成」，搜索「控客」。

### HACS 自定义仓库

1. 在 HACS 的「自定义存储库」中添加 `https://github.com/YyyQq-C/home-assistant-konke`，类别选择「集成」。
2. 下载「控客 Konke」，重启 Home Assistant，再通过设备与服务添加集成。

也可使用 My Home Assistant 快捷链接（需已安装 HACS）：

[![在 Home Assistant 中打开 HACS 仓库](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=YyyQq-C&repository=home-assistant-konke&category=integration)

本项目提供 HACS 自定义仓库安装结构；不表示已经进入 HACS 默认列表。

## 核对主机公钥并配置

SSH 主机公钥用于确认连接的是你的控客主机，不能以登录密码代替。先通过设备控制台、已信任的管理连接或独立可信渠道获得完整公钥及指纹，再与网络采集结果核对。

以下命令适用于安装了 OpenSSH 的 Windows PowerShell 或 Linux/macOS 终端，只采集公钥和显示指纹，不操作设备。请把 `<网关地址>` 和 `<SSH端口>` 替换为自己的值。`ssh-keyscan` 结果本身未经认证，不能直接当作可信依据。

```sh
ssh-keyscan -p <SSH端口> <网关地址> > gateway-host-keys.txt
ssh-keygen -lf gateway-host-keys.txt
```

指纹与可信来源一致后，从对应行中提取**算法名和 Base64 公钥**，例如 `ssh-rsa <你核对后的Base64公钥>`，不要包含前面的主机地址或尖括号占位符。

配置界面填写：

| 字段 | 内容 |
| --- | --- |
| 控客地址 | 自己的网关 IP 或主机名，无默认家庭地址 |
| SSH 端口 | 通常为 22，按实际配置填写 |
| SSH 用户 | 有上述权限的账号，默认 `root` |
| SSH 密码 | 该账号实际密码 |
| 已核对的主机公钥 | 算法名、空格、Base64 公钥 |

配置验证仅查询设备，不下发控制指令。主机公钥不匹配时拒绝连接；不要通过关闭校验解决。主机重装或换机后，先重新核对公钥，再更新配置。

### SSH 登录参考

以下账号密码已在本项目的 KK-CC-G12W 验证环境中使用，仅供有权管理自己设备的用户参考，不保证适用于其他设备或固件，也不代表所有控客产品的统一默认密码。

| SSH 用户 | 参考密码 | 验证范围 |
| --- | --- | --- |
| `root` | `p9z34c` | 本项目已验证的 KK-CC-G12W 环境 |

请以自己设备的实际 SSH 凭据为准，并在启用远程访问前修改公开参考密码。集成不会自动填入或尝试此密码；原厂回环协议的 `local/local` 用于内部服务登录，不可填作 SSH 凭据。

## 使用

在 HA 原生温控卡片中使用空调和地暖，在风扇卡片中使用新风。也可调用标准 `climate.set_temperature`、`climate.set_hvac_mode`、`climate.set_fan_mode`、`fan.set_percentage` 等动作，选择自己实际的实体。

单设备操作只针对所选节点。调整空调温度保留原开关、模式与风速。状态来自原厂缓存，控制确认和缓存更新之间可能有延迟；异常可查看 HA 日志中的 `custom_components.konke_local`。

新增原厂设备后可重新加载集成发现；设备离线、原厂缓存缺失或 SSH 读取失败时，实体可能显示不可用。没有映射未经验证的新风模式、湿度或其他产品功能。

## 更新、迁移与卸载

- 更新前备份 HA 配置。手动替换 `custom_components/konke_local`，或通过 HACS 更新，然后重启 HA。
- 从使用同一 `konke_local` 域名的旧版本迁移时，保留原配置项、网关地址和实体注册表，仅替换组件文件。域名和实体唯一标识算法未改变；不要先删除集成，否则用户自定义实体名称可能丢失。
- 当前未提供凭据编辑选项界面。密码、公钥或地址变化时，核对新值后删除并重新添加配置项；此操作可能影响实体名称及自动化引用，请先记录并在完成后核对。
- 卸载：先在设备与服务中删除集成，再删除 `custom_components/konke_local`（或从 HACS 卸载），最后重启 HA。不会删除控客原厂配置。

## 排障与反馈

- 无法连接：检查 HA 到网关的路由、SSH 端口、凭据、公钥以及账号的转发权限。
- 找不到设备：检查原厂系统是否已配置支持的设备、SQLite 路径和表结构是否与验证环境一致。
- 设备不可用：先确认原厂应用中的在线状态；不要把设定温度误当作当前室温。
- 控制超时：原厂服务可能已执行但未及时返回确认，先核对实际状态，避免重复操作。

提交问题请说明型号、固件（若可查）、HA 版本、操作步骤和脱敏日志；不要上传 SSH 密码、完整公钥、家庭地址、数据库或设备快照。

## 开发验证

以下命令适用于已安装 Python 3.13 的开发终端，会建立虚拟环境、安装依赖并运行离线检查；不连接或操作真实设备。Windows 激活环境使用 `.venv\Scripts\Activate.ps1`。

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python scripts/validate_release.py
```

离线测试覆盖协议分帧、单设备隔离、空调未改字段保留、离线拒绝、温度范围及主机公钥拒绝策略。自动检查不替代其他型号的真实 HA 安装测试。

仓库结构参考 [HACS 集成要求](https://www.hacs.xyz/docs/publish/integration/) 和 [HA 清单规范](https://developers.home-assistant.io/docs/creating_integration_manifest/)。自绘图标为社区项目图形，并非控客官方商标。代码和图标采用 [MIT](LICENSE) 许可证。
