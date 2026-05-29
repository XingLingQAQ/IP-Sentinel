# 🛡️ IP-Sentinel (分布式 IP 哨兵集群)

![Agent Installs](https://img.shields.io/endpoint?url=https://ip-sentinel-count.samanthaestime296.workers.dev/stats/agent)
![Master Commands](https://img.shields.io/endpoint?url=https://ip-sentinel-count.samanthaestime296.workers.dev/stats/master)
![License](https://img.shields.io/github/license/XingLingQAQ/IP-Sentinel)

> **一个极度轻量、零感知、支持中枢遥控的 VPS IP 自动化养护与区域纠偏引擎。**
> **💡 提示：如果本项目提升了您的节点稳定性，请点击右上角点亮 🌟 Star！您的支持是我们持续研发和维护指纹库的核心动力。**

📢 官方战术交流频道: 🛰️ [IP-Sentinel Matrix](https://t.me/IP_Sentinel_Matrix)

专为解决 VPS IP 被 Google 等数据库错误定位到中国大陆/香港（俗称“送中”）等问题而生。IP-Sentinel 已从单机脚本全面跃升为 **Master-Agent 分布式架构**。它像影子一样潜伏在全球各地的服务器后台，通过高度拟真的真实用户行为为你默默积累 IP 权重，并允许你通过 Telegram 随时随地对整个舰队进行毫秒级“点名”与“遥控”。

## ✨ 核心极客特性 (Core Architecture)

- 📊 **深海声呐全维探针 (Deep Sea Sonar v4.0.4)**：内嵌强效正则去污的 JSON 提取引擎，无损展现免掩码的真实 IP 情报。聚合 Scamalytics、AbuseIPDB 等五大权威防欺诈库，精准嗅探代理/VPN特征、25端口及流媒体原生解锁状态，并自带 Google “送中”高危预警与污染趋势图谱。
- ⚡ **无损高并发引擎 (WAL Concurrency)**：司令部 SQLite 数据库全面激活 `WAL` (Write-Ahead Logging) 模式与毫秒级排队算法。即使对 500 台边缘节点发起全军总攻，也能完美规避 `database is locked` 与 Telegram `429` 拦截。
- 🪶 **抽脂级极简部署 (Zero-Bloat Native)**：全栈剔除第三方依赖，基于 Python3 原生标准库运行。安装强制注入 `--no-install-recommends` 防捆绑参数。无论是 128MB 内存的极简 NAT，还是 Alpine 游击队容器，均可如丝般顺滑运行。
- 🎛️ **扁平化指挥矩阵 (Flat Command Matrix)**：引入扁平化四级战区降维视图与双轨身份制。深度定制 Inline Keyboard 逃生舱交互，支持原位丝滑重绘 (In-place UI Edit)，实现毫秒级模块热启停与跨地域深海声呐投放。
- 🔄 **全栈零信任 OTA 引擎 (Zero-Trust OTA Upgrade)**：首创双端物理熔断机制。长官可通过私有中枢，一键向全舰队下发静默热重载指令；更支持**「司令部金蝉脱壳」**，实现真正的全栈去 SSH 化运维。
- 🛡️ **SSOT 溯源与热更新装甲 (Smooth Upgrade Engine)**：全系脚本彻底消灭硬编码，动态抓取云端版本信标。自带状态机嗅探逻辑，即便是手动在老节点执行安装，也仅需回车瞬间完成配置继承与无损换代。
- 🗺️ **全球拓扑矩阵与活体词库 (Global Nexus)**：接入 GitHub Actions 云端兵工厂，每日静默同步全球各大区真实热搜榜单与高权重本土站点，让伪装行为永远贴合当地网络脉搏。
- 👻 **绝对时空对齐与高频错峰 (UTC-Seeded Scheduling)**：摒弃传统随机轮询，全栈强制接管底层时钟为**绝对 UTC 时间**。全舰队以 **20 分钟 (每日 72 次)** 的极高密度进行养护巡逻，叠加基于部署锚点的天然削峰与随机防并发休眠，完美化解十万级集群的“惊群效应”与 API 熔断。
- 🖧 **极速预检与三级容灾架构 (Fail-Fast & Fallback)**：底层引擎强力接管发包参数 (`--interface`) 的同时，创新引入 **4 秒极速预检 (Fail-Fast)** 雷达与**三级阶梯脱壳**机制。无论是纯 IPv6 孤岛、WARP 劫持死锁还是复杂 NAT 嵌套，系统均能瞬间避开网络黑洞，彻底杜绝探针假死与流量溢出。

**—— 💎 骨干基建特征 ——**
- 🏭 **全自动云端军工厂 (CI/CD Data Factory)**：依托 GitHub Actions 构建双轨无人值守流水线。**每月 1 日**批量锻造 4000+ 带有绝对物理分区的原生终端指纹库；**每日凌晨 (UTC)** 实时抓取全球各战区 Google 真实热搜榜单与本土骨干新闻 RSS。为前线舰队源源不断地输送最鲜活的伪装弹药。
- 🔒 **叹息之墙 (Zero-Trust HMAC)**：底层通讯引入 时间戳 + HMAC-SHA256 军用级动态签名。指令有效期仅 60 秒（阅后即焚），未授权请求直接触发系统级 403 物理熔断，彻底免疫中间人抓包与重放攻击。
- ☁️ **云端中枢 (Public Master)**：官方公共机器人 [@OmniBeacon_bot](https://t.me/OmniBeacon_bot) ，新手免自建，一键接入极速入伍！同时支持硬核极客私有化 SQLite 分布式部署。
- 👁️‍🗨️ **玻璃房透明遥测 (Glasshouse)**：基于 Cloudflare Workers 的全透明计数中枢，绝对零隐私收集，仅作原子累加，底层网关源码全开源。

## 📂 项目架构 (Monorepo)

本项目采用企业级的“主从控制”与“冷热数据分离”双重架构：

```text
📦 IP-Sentinel
 ┣ 📂 .github/workflows/      # 🏭 自动化兵工厂：每月定时触发指纹生成的 CI/CD 流水线
 ┣ 📂 master/                 # 🧠 司令部：SQLite 存储 (含 ip_trend_log 趋势跟踪表)、TG 监听与 Webhook 调度
 ┣ 📂 core/                   # 🛡️ 边缘哨兵：Webhook 被动监听、哈希锚定执行引擎 (集成深海声呐探测模块)
 ┣ 📂 scripts/                # 🐍 兵工厂引擎：基于 Python 的多物理分区 UA 生成器
 ┣ 📂 data/                   # 🗂️ 全球数据规则库 (动态拓扑)
 ┃  ┣ 📜 map.json             # 🌍 全球区域大脑 (v3.5.0 大洲战区拓扑)
 ┃  ┣ 📂 regions/             # 🧊 冷数据：按 [国家/省州/城市] 深度细分的 LBS 锚点
 ┃  ┣ 📂 keywords/            # 🔥 热数据：按国家归类的动态搜索词库 (OTA 自动更新)
 ┃  ┗ 📜 user_agents.txt      # 🔥 热数据：由兵工厂每月锻造的绝对坐标专属设备库
 ┣ 📜 version.txt             # 🚩 双端版本信标：Agent/Master 独立解耦的 KV 环境配置
 ┗ 📂 telemetry/              # 👁️‍🗨️ 玻璃房计划：Cloudflare Workers 透明计数器网关源码
```

## 🚀 极速部署 (Quick Start)
> 🛡️ **跨平台装甲支持**：Debian / Ubuntu / CentOS / RHEL / Alpine Linux / Arch Linux
系统现提供两种接入模式，请根据您的战术需求选择：

### 🔹 模式 A：私有独立模式 (全自主、强烈推荐)
适合追求绝对数据隐私与舰队最高控制权的领主。

> ☢️ **核按钮系统已就绪**：采用私有部署，您将解锁 **OTA 远程静默升级** 权限！所有私有前线节点均可通过您的 TG 面板实现一键全网代码热重载换代！

- **部署 Master (中枢大脑)**：找一台 VPS 作为司令部（仅需部署一台），执行：
- [官方部署教程](https://blog.iot-architect.com/engineering-practice/ip-sentinel-master-deployment-guide/)
```bash
curl -fsSL https://raw.githubusercontent.com/XingLingQAQ/IP-Sentinel/main/master/install_master.sh -o /tmp/ins_master.sh && sudo bash /tmp/ins_master.sh
```
- 部署 Agent (边缘哨兵)：在需要养护的机器上执行 Agent 脚本，安装时选择私有独立中枢，并分别输入您自建机器人的 [Token](https://blog.iot-architect.com/engineering-practice/create-private-telegram-bot-via-botfather) 以及您的个人 [Chat ID](https://blog.iot-architect.com/engineering-practice/get-telegram-personal-id-via-userinfobot) ：
- [官方部署教程](https://blog.iot-architect.com/engineering-practice/ip-sentinel-installation-and-upgrade-guide/)
```Bash
curl -fsSL https://raw.githubusercontent.com/XingLingQAQ/IP-Sentinel/main/core/install.sh -o /tmp/ins_agent.sh && sudo bash /tmp/ins_agent.sh
```
- 激活节点：安装完成后，您的手机会收到一条 #REGISTER# 注册暗号，将其转发给您自己的机器人即可完成编队入库。

### 🔸 模式 B：官方公共模式 (最简体验)
适合不想折腾、只想快速体验养护效果的新兵。

- 关注机器人：在 TG 中关注官方安全网关 [@OmniBeacon_bot](https://t.me/OmniBeacon_bot) 并发送 /start。

- 部署 Agent：在目标 VPS 上执行以下指令，安装过程中选择官方公共网关，并输入您的 Chat ID：
- [官方部署教程](https://blog.iot-architect.com/engineering-practice/deploy-ip-sentinel-official-gateway/)
```Bash
curl -fsSL https://raw.githubusercontent.com/XingLingQAQ/IP-Sentinel/main/core/install.sh -o /tmp/ins_agent.sh && sudo bash /tmp/ins_agent.sh
```
- 激活节点：同上，将收到的暗号转发给官方机器人即可。

### 🐳 模式 C：Docker 容器化部署 Master 司令部 (推荐生产环境)
适合追求环境隔离、标准化运维与快速迁移的运维指挥官。将 Master 中枢容器化部署，彻底消除环境差异问题，实现真正的 **基础设施即代码 (IaC)**。

> 🛡️ **多架构装甲支持**：官方 Master 镜像提供 `linux/amd64` 与 `linux/arm64` 双平台预构建，兼容 x86 服务器与 ARM 开发板。
>
> 💡 **架构说明 (v5.0.0 Webhook 事件驱动架构)**：
> - Docker 容器化部署**仅适用于 Master 司令部**。Master 内部运行 `webhook_master.py` (Python3 HTTP 服务)，监听 **端口 7860**，通过 Telegram Webhook 接收消息推送 (取代旧版长轮询机制)。
> - **Agent 不需要 Docker 部署**。Agent 边缘节点必须直接安装在目标 VPS 裸金属上 (通过模式 A/B 的 `install.sh`)，原因：Agent 需要直接感知宿主机真实网络环境 (公网 IP 探测、端口监听、路由表绑定等)，Docker 网络隔离会导致 IP 检测失真。
> - **支持 HuggingFace Spaces 部署**：Master 可作为 Docker Space 部署在 [HuggingFace Spaces](https://huggingface.co/spaces) 上 (免费 GPU/CPU Spaces 均可)，无需自备服务器，平台自动提供 HTTPS 公网 URL。

---

#### 📋 前置条件 (Prerequisites)

| 组件 | 最低版本 | 安装参考 |
|------|---------|---------|
| Docker Engine | 20.10+ | [官方安装文档](https://docs.docker.com/engine/install/) |
| Docker Compose | v2.0+ (插件模式) | [Compose 安装指南](https://docs.docker.com/compose/install/) |

验证安装：
```bash
docker --version        # Docker version 20.10+
docker compose version  # Docker Compose version v2.x.x
```

---

#### 🚀 方式一：Docker Compose 部署 (推荐)

> 使用 Docker Compose 编排 Master 司令部，一条命令完成部署。Master 容器内部运行 `webhook_master.py` (端口 7860)，启动时自动注册 Telegram Webhook。Agent 仍通过 `install.sh` 在各边缘 VPS 上独立部署。

**第一步：克隆战术仓库**
```bash
git clone https://github.com/XingLingQAQ/IP-Sentinel.git
cd IP-Sentinel
```

**第二步：创建环境变量配置文件**

在项目根目录创建 `.env` 文件，填入中枢作战参数：
```bash
cat > .env << 'EOF'
# ==================================================
# IP-Sentinel Master v5.0.0 Docker 部署环境变量配置
# (Webhook 事件驱动架构)
# ==================================================

# ---------- [必填] Telegram 通讯链路 ----------
# 通过 @BotFather 创建私有机器人后获取的 Bot Token
# 获取方法: 在 TG 中搜索 @BotFather -> /newbot -> 复制 HTTP API Token
TG_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz

# 管理员个人 Chat ID (Master 启动后发送指令的目标用户)
# 获取方法: 在 TG 中搜索 @userinfobot -> 发送任意消息 -> 复制 Id 字段
CHAT_ID=987654321

# ---------- [必填] Webhook 公网接入地址 ----------
# Master 对外可达的 HTTPS URL (Telegram 服务器将向此地址推送消息)
# 必须为 HTTPS，且该地址能从公网访问到容器的 7860 端口
# 示例 (自有域名): https://sentinel.your-domain.com
# 示例 (HuggingFace Spaces): https://username-ip-sentinel.hf.space
WEBHOOK_URL=https://your-domain.com

# ---------- [可选] Webhook 安全秘钥 ----------
# 用于验证来自 Telegram 的 Webhook 请求 (防止伪造)
# 留空则容器启动时自动生成随机 256-bit 密钥
# WEBHOOK_SECRET=your-custom-secret-here

# ---------- [可选] 中枢 OTA 自更新 ----------
# 设为 true 后，可通过 TG 面板一键升级 Master 自身 (金蝉脱壳)
# 首次部署建议保持 false，待稳定后再开启
ENABLE_MASTER_OTA=false

# ---------- [可选] 官方公共网关模式 ----------
# 仅官方运营者需设为 true，私有部署用户请保持 false
IS_OFFICIAL_GATEWAY=false
EOF
```

> 💡 **安全提示**：`.env` 文件包含敏感凭据 (Token、Webhook 地址)，请确保不要将其提交到 Git 仓库。项目 `.gitignore` 已默认忽略该文件。

**第三步：启动 Master 中枢**
```bash
docker compose up -d master
```

> 💡 容器启动时会自动向 Telegram 注册 Webhook 地址 (调用 `setWebhook` API)，无需手动配置。

**第四步：确认中枢运行状态**
```bash
# 查看容器运行状态
docker compose ps

# 实时查看中枢日志 (Ctrl+C 退出)
docker compose logs -f master

# 验证 Webhook 服务健康状态 (应返回 {"status":"ok","version":"5.0.0"})
curl http://localhost:7860/health
```
正常启动后，日志将显示：
```
[Docker] 正在启动 IP-Sentinel Master 控制中枢 (Webhook 模式)...
[Docker] Webhook 注册成功: https://your-domain.com/webhook
[Webhook Master] v5.0.0 listening on 0.0.0.0:7860
[Webhook Master] Endpoints: POST /webhook, POST /heartbeat, GET /health
```

**第五步：部署 Agent 并激活编队**

在需要养护 IP 的各台 VPS 上，按照上方 **模式 A** 或 **模式 B** 的方式安装 Agent。Agent 启动后会向你的 TG 发送 `#REGISTER#` 注册暗号，将其转发给你的机器人即可完成编队入库。

> 💡 **关于 WEBHOOK_URL 获取**：如果你使用自有服务器部署 Master，需要为该服务器配置反向代理 (Nginx/Caddy) 并绑定域名 + SSL 证书，将 HTTPS 流量转发到容器的 7860 端口。如果使用 HuggingFace Spaces，平台会自动分配 `https://username-space-name.hf.space` 格式的公网 HTTPS 地址。

---

#### 🧠 方式二：Docker Run 直接部署 (无需 Compose)

> 适合不想克隆仓库、直接一行命令拉起中枢的极简主义者。

```bash
docker run -d \
  --name ip-sentinel-master \
  --restart unless-stopped \
  -p 7860:7860 \
  -e TG_TOKEN="你的Bot_Token" \
  -e CHAT_ID="你的Chat_ID" \
  -e WEBHOOK_URL="https://your-domain.com" \
  -e ENABLE_MASTER_OTA="false" \
  -e IS_OFFICIAL_GATEWAY="false" \
  -v sentinel-data:/opt/ip_sentinel_master/data \
  ghcr.io/xinglingqaq/ip-sentinel-master:latest
```

**参数解读：**
| 参数 | 说明 |
|------|------|
| `-p 7860:7860` | 映射 Webhook HTTP 服务端口 (Telegram 推送入口) |
| `--restart unless-stopped` | 异常退出自动拉起，手动 stop 除外 |
| `-e TG_TOKEN=xxx` | 传入 Telegram Bot Token (必填) |
| `-e CHAT_ID=xxx` | 传入管理员 Chat ID (必填) |
| `-e WEBHOOK_URL=xxx` | Master 的公网 HTTPS 地址，Telegram 向此推送消息 (必填) |
| `-e ENABLE_MASTER_OTA=false` | 中枢 OTA 自更新开关 |
| `-e IS_OFFICIAL_GATEWAY=false` | 官方网关模式开关 (私有用户保持 false) |
| `-v sentinel-data:/opt/ip_sentinel_master/data` | 将 SQLite 数据库挂载至命名卷，容器重建数据不丢失 |

---

#### 📦 方式三：使用预构建镜像 (GHCR)

官方 Master 镜像托管于 GitHub Container Registry，支持版本锁定与滚动更新：

```bash
# 拉取最新版 Master 镜像
docker pull ghcr.io/xinglingqaq/ip-sentinel-master:latest

# 拉取指定版本镜像 (推荐生产环境锁定版本号)
docker pull ghcr.io/xinglingqaq/ip-sentinel-master:5.0.0
```

> 镜像在每次发布新版本 Tag (`v*`) 时由 GitHub Actions 自动构建并推送，同时生成 `linux/amd64` 与 `linux/arm64` 双平台产物。

---

#### 📊 环境变量完整参考表 (Environment Variables Reference)

以下为 Master 司令部 Docker 部署所支持的全部环境变量：

| 变量名 | 必填/可选 | 默认值 | 说明 |
|--------|----------|--------|------|
| `TG_TOKEN` | **必填** | - | Telegram Bot Token。通过 @BotFather 创建机器人后获取，格式为 `数字:字母串`。这是 Master 与 Telegram 通讯的唯一凭证 |
| `CHAT_ID` | **必填** | - | 管理员个人 Telegram Chat ID。通过 @userinfobot 获取。Master 将向此 ID 发送战报与节点注册通知 |
| `WEBHOOK_URL` | **必填** | - | Master 的公网 HTTPS 地址 (如 `https://sentinel.example.com` 或 `https://user-ip-sentinel.hf.space`)。Telegram 服务器将向 `{WEBHOOK_URL}/webhook` 推送消息更新。必须从公网可达且为 HTTPS 协议 |
| `WEBHOOK_SECRET` | 可选 | *(自动生成)* | Webhook 请求验证密钥。Telegram 发送 Webhook 时在 Header 中携带此值用于身份验证。留空时容器每次启动自动生成随机 256-bit 密钥 |
| `ENABLE_MASTER_OTA` | 可选 | `false` | 是否启用中枢 OTA 自更新 (金蝉脱壳)。设为 `true` 后可通过 TG 面板一键升级 Master 版本 |
| `IS_OFFICIAL_GATEWAY` | 可选 | `false` | 是否以官方公共网关模式运行。仅 [@OmniBeacon_bot](https://t.me/OmniBeacon_bot) 官方运营者使用，私有部署请勿开启 |
| `MASTER_VERSION` | 可选 | `5.0.0` | Master 版本号标识，一般无需手动指定，由镜像内置 |

> 💡 **获取 TG_TOKEN 的完整步骤：**
> 1. 在 Telegram 中搜索 [@BotFather](https://t.me/BotFather)
> 2. 发送 `/newbot`，按提示设定机器人名称与用户名
> 3. 创建成功后复制返回的 `HTTP API Token` (即 `TG_TOKEN`)
> 4. 向你新建的机器人发送 `/start` 激活对话

> 💡 **获取 CHAT_ID 的完整步骤：**
> 1. 在 Telegram 中搜索 [@userinfobot](https://t.me/userinfobot)
> 2. 发送任意消息，机器人会回复你的用户信息
> 3. 复制 `Id` 字段的数字 (即 `CHAT_ID`)

---

#### 💾 数据持久化与卷管理 (Volumes & Persistence)

Master 容器的核心数据存储在 SQLite 数据库中，通过 Docker 命名卷实现持久化：

| 命名卷 | 容器内路径 | 用途 |
|--------|-----------|------|
| `sentinel-data` | `/opt/ip_sentinel_master/data` | Master SQLite 数据库 (节点注册表 `nodes` + IP 趋势日志 `ip_trend_log`) |

**数据库包含的关键表：**
- `nodes` - 全舰队节点注册信息 (IP、端口、地区、别名、模块开关状态、最后心跳时间)
- `ip_trend_log` - IP 质量趋势历史数据 (Scam 分数、Google/Netflix/GPT 解锁状态)

**备份数据：**
```bash
# 方法 A：使用 docker cp 导出数据库文件到宿主机
docker cp ip-sentinel-master:/opt/ip_sentinel_master/data/sentinel.db ./backup_sentinel.db

# 方法 B：使用 bind mount 替代命名卷 (直接映射宿主机目录，方便定时备份)
# 修改 docker-compose.yml 中的 volumes 配置:
#   volumes:
#     - ./data/master:/opt/ip_sentinel_master/data
```

**恢复数据：**
```bash
# 将备份文件恢复到容器
docker cp ./backup_sentinel.db ip-sentinel-master:/opt/ip_sentinel_master/data/sentinel.db

# 重启容器使数据库生效
docker restart ip-sentinel-master
```

> 💡 使用命名卷时，即使执行 `docker compose down` 销毁容器，数据仍安全保存在卷中。仅当显式执行 `docker compose down -v` 时才会清除卷数据。

---

#### 🔧 常用运维命令 (Operations Commands)

```bash
# ---------- 日志查看 ----------
docker compose logs -f master          # 实时跟踪中枢日志 (Ctrl+C 退出)
docker compose logs --tail=100 master  # 查看最近 100 行日志
docker logs ip-sentinel-master         # 不使用 Compose 时查看日志

# ---------- 服务控制 ----------
docker compose restart master          # 重启中枢服务
docker compose stop master             # 停止中枢 (保留容器)
docker compose down                    # 停止并移除容器 (保留数据卷)
docker compose down -v                 # 停止并移除容器与数据卷 (!! 慎用 - 会丢失数据库)

# ---------- 滚动更新 ----------
docker compose pull master             # 拉取最新 Master 镜像
docker compose up -d master            # 使用新镜像重建容器

# ---------- 调试排障 ----------
docker exec -it ip-sentinel-master bash                    # 进入中枢容器 Shell
docker exec -it ip-sentinel-master cat /opt/ip_sentinel_master/master.conf  # 查看生成的配置
docker inspect ip-sentinel-master                          # 查看容器详细配置与网络信息
```

---

#### 🆙 Docker 升级指南 (Docker Upgrade)

```bash
# 一键拉取最新镜像并无缝重建 Master 容器
docker compose pull master && docker compose up -d master
```

升级过程中数据卷不受影响，SQLite 数据库安全保留。容器会在数秒内完成替换，中枢启动时自动重新注册 Telegram Webhook 并恢复 HTTP 事件驱动服务。

如需回退至特定版本，修改 `docker-compose.yml` 中的 `image` 字段：
```yaml
services:
  master:
    image: ghcr.io/xinglingqaq/ip-sentinel-master:5.0.0
```

然后执行 `docker compose up -d master` 完成版本锁定。

> 💡 **Agent 升级**：Agent 仍通过传统方式升级 (OTA 远程静默升级或 SSH 终端重新运行 `install.sh`)，详见下方「架构级无损热升级指引」章节。

---

#### 🚨 故障排查 (Troubleshooting)

| 现象 | 排查方向 |
|------|---------|
| 容器启动后立即退出 | 执行 `docker logs ip-sentinel-master` 查看错误。最常见原因：`TG_TOKEN` 或 `WEBHOOK_URL` 未设置 |
| 日志显示 "Webhook 注册可能失败" | 检查 `WEBHOOK_URL` 是否为合法 HTTPS 地址、该地址是否从公网可达 (Telegram 服务器需能访问)、SSL 证书是否有效 |
| 容器反复重启 (restart loop) | 检查 `TG_TOKEN` 是否有效 (未被 @BotFather revoke)、`WEBHOOK_URL` 是否已配置 |
| 发送命令无响应 | 确认 `WEBHOOK_URL` 配置正确且端口 7860 已对外暴露。执行 `curl https://your-domain.com/health` 验证连通性 |
| Permission denied 权限拒绝 | 确保使用官方镜像 (脚本已预设 `chmod +x`)。若使用 bind mount，检查宿主机目录权限 |
| 数据库锁定 (database is locked) | 中枢已内置 WAL 模式处理并发。若仍出现，检查是否有多个容器挂载了同一数据卷 |
| Agent 注册消息未收到 | 确认 Master 容器正常运行中，检查 Agent 侧 Token 和 Chat ID 是否与 Master 一致 |
| 节点长时间显示离线 | Master 正常但 Agent 心跳中断，登录 Agent 所在 VPS 检查 `agent_daemon.sh` 进程状态 |

**快速诊断流程：**
```bash
# 1. 检查容器状态与退出码
docker compose ps -a

# 2. 查看最近启动日志定位错误
docker compose logs --tail=50 master

# 3. 进入容器验证配置是否正确生成
docker exec -it ip-sentinel-master cat /opt/ip_sentinel_master/master.conf

# 4. 验证 Webhook 服务健康状态
curl http://localhost:7860/health

# 5. 验证 Telegram API 连通性
docker exec -it ip-sentinel-master curl -s "https://api.telegram.org/bot你的Token/getMe"

# 6. 检查 Webhook 注册状态
docker exec -it ip-sentinel-master curl -s "https://api.telegram.org/bot你的Token/getWebhookInfo"
```

---

#### 💓 Agent 心跳配置 (Heartbeat - 可选)

v4.2.0+ 版本的 Agent 支持向 Master 发送定期心跳 (每 10 分钟一次)。心跳的主要作用：
- 在 HuggingFace Spaces 等平台上防止容器因无流量而休眠
- 让 Master 实时更新节点 `last_seen` 时间戳

**配置方法**：在 Agent 所在 VPS 的配置文件 `/opt/ip_sentinel/config.conf` 中添加：
```bash
MASTER_WEBHOOK_URL="https://your-domain.com"
```

将地址替换为你部署 Master 时设置的 `WEBHOOK_URL` 值。

> 💡 **向下兼容**：此配置为可选项。旧版本 Agent (v4.1.x 及更早) 无此字段也能正常工作，所有 TG 管理功能不受影响。新安装的 Agent (通过 `install.sh` v4.2.0+) 会在安装时询问是否配置此项。

---

## 🆙 架构级无损热升级指引 (Upgrade Guide)

### 📡 方式一：OTA 远程静默升级 (私有中枢专属)
如果您是私有中枢领主，当司令部首页 (`/start`) 或每日战报提示发现新版本时：

1. **升级 Master 司令部自身**：在司令部顶级菜单，点击最上方的 `[ 🆙 升级司令部至 vX.X.X ]`。中枢将释放幽灵进程静默重构，数秒后向您发送捷报。
2. **升级全舰队 Agent**：在司令部顶级菜单，点击 `[ ☢️ 全舰队 OTA 热重载 ]`。
3. **升级单节点 Agent**：进入 `🌍 全球战区雷达` -> 选择目标节点 -> 在统一终端面板点击 `[ 🆙 OTA 静默升级 ]`。
*(⚠️ 节点收到指令后会在后台挂起静默拉取，全程无需登录 SSH，完成后将主动发回心跳确认！)*

### 💻 方式二：SSH 终端平滑直装 (适用于官方网关或老旧节点)
如果您的节点不支持 OTA，或者您的节点版本过于陈旧 (如 v3.3.1)：

- 登录该节点的 SSH 终端，再次运行上面的 core/install.sh 官方安装指令。

- 安装引擎自带状态机嗅探逻辑，它会自动读取老旧数据，您只需一路回车，3 秒即可在本地完成配置继承、数据同步与新内核的无损覆盖热重载！

## 🗑️ 一键无痕卸载
如果你需要清理某个边缘节点，只需重新运行 `core/install.sh` 并选择 **[2]**，或直接在节点终端执行：

```Bash
bash /opt/ip_sentinel/core/uninstall.sh

```

## 🧓 传家宝老旧系统专用通道 (Debian 9)

如果你的小鸡系统版本过低（如 Debian 9），由于官方 APT 源已关闭且 Python 版本过旧，无法使用主线版本，请使用 **Legacy 兼容分支** 部署。
*(注意：该分支仅作基础维护，不享受新功能迭代，请尽可能升级你的系统)*

```bash
bash <(curl -sL https://raw.githubusercontent.com/XingLingQAQ/IP-Sentinel/legacy/core/install.sh)
```

## 📡 战术联络 (Community)

如果你在使用过程中遇到任何疑难杂症，或者想围观大佬们的养护战报，欢迎加入我们的基地：
- Telegram 频道: [@IP_Sentinel_Matrix](https://t.me/IP_Sentinel_Matrix)

## 🤝 参与贡献 (Contributors)

**🌟 感谢以下所有为 IP-Sentinel 添砖加瓦的指挥官们！** 你们的每一次 PR 都在让这艘战舰的全球雷达覆盖得更广。

<a href="https://github.com/XingLingQAQ/IP-Sentinel/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=XingLingQAQ/IP-Sentinel" alt="Contributors" />
</a>

如果你想为项目增加新的节点区域（例如德国、英国、大洋洲等），或者提供更丰富的本土化搜索词库，非常欢迎提交 Pull Request！


> - 感谢 @xykt 本项目IP质量检测采用[xykt/IPQuality](https://github.com/xykt/IPQuality) 脚本！

**💡 全球节点贡献规范：**
1. 在 `data/regions/国家代码/省州代码/` 目录下新增对应城市的配置 `.json`。
2. 在 `data/keywords/` 目录下新增或完善配套国家的词库 `kw_XX.txt`。
3. **最重要的一步：** 在 `data/map.json` 中登记你的国家、省州与城市信息。安装脚本将自动读取地图，在全球雷达中点亮你的节点！

## ⚠️ 免责声明

本项目仅供网络原理研究、个人 VPS 维护学习使用。请遵守当地法律法规及目标服务商的 TOS（服务条款），切勿用于恶意高频请求或任何非法用途。使用者需自行承担因不当使用造成的 IP 封禁或其他相关风险。

## 保持联系

[![Blog](https://img.shields.io/badge/Blog-个人博客-blue)](https://blog.iot-architect.com)

如果你觉得这个项目对你有帮助，欢迎关注我的个人博客，我会定期分享技术教程。


## Stargazers over time
[![Stargazers over time](https://starchart.cc/XingLingQAQ/IP-Sentinel.svg?variant=adaptive)](https://starchart.cc/XingLingQAQ/IP-Sentinel)