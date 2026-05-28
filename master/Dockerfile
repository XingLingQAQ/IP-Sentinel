# ==========================================================
# IP-Sentinel Master 控制中枢 Docker 镜像
# 基于 Debian Bookworm 精简版，提供最小化运行时环境
# ==========================================================

FROM debian:bookworm-slim

LABEL maintainer="IP-Sentinel"
LABEL description="IP-Sentinel Master 控制中枢 - Telegram Bot 长轮询服务"

# [依赖装甲] 安装中枢运行所需的全部系统组件
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    jq \
    sqlite3 \
    cron \
    procps \
    openssl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# [目录构建] 创建中枢工作目录与数据持久化挂载点
RUN mkdir -p /opt/ip_sentinel_master/data

# [核心部署] 复制中枢引擎与入口脚本
COPY master/tg_master.sh /opt/ip_sentinel_master/tg_master.sh
COPY master/docker-entrypoint.sh /opt/ip_sentinel_master/docker-entrypoint.sh

# [权限加固] 确保脚本可执行
RUN chmod +x /opt/ip_sentinel_master/tg_master.sh \
    && chmod +x /opt/ip_sentinel_master/docker-entrypoint.sh

# [数据卷声明] SQLite 数据库持久化存储
VOLUME ["/opt/ip_sentinel_master/data"]

WORKDIR /opt/ip_sentinel_master

ENTRYPOINT ["/opt/ip_sentinel_master/docker-entrypoint.sh"]
