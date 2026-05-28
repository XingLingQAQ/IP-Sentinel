# ==========================================================
# IP-Sentinel Agent 边缘节点 Docker 镜像
# 基于 Debian Bookworm 精简版，提供最小化运行时环境
# ==========================================================

FROM debian:bookworm-slim

LABEL maintainer="IP-Sentinel"
LABEL description="IP-Sentinel Agent 边缘节点 - Webhook 监听 + 定时养护引擎"

# [依赖装甲] 安装边缘节点运行所需的全部系统组件
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    jq \
    cron \
    procps \
    python3 \
    openssl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# [目录构建] 创建边缘节点标准目录结构
RUN mkdir -p /opt/ip_sentinel/core \
    && mkdir -p /opt/ip_sentinel/data \
    && mkdir -p /opt/ip_sentinel/logs

# [核心部署] 复制边缘节点引擎脚本
COPY core/agent_daemon.sh /opt/ip_sentinel/core/
COPY core/runner.sh /opt/ip_sentinel/core/
COPY core/updater.sh /opt/ip_sentinel/core/
COPY core/tg_report.sh /opt/ip_sentinel/core/
COPY core/mod_google.sh /opt/ip_sentinel/core/
COPY core/mod_trust.sh /opt/ip_sentinel/core/
COPY core/mod_quality.sh /opt/ip_sentinel/core/
COPY core/uninstall.sh /opt/ip_sentinel/core/

# [数据部署] 复制关键词库、地区规则、UA 池等冷数据
COPY data/ /opt/ip_sentinel/data/

# [入口脚本] 复制容器启动入口
COPY core/docker-entrypoint.sh /opt/ip_sentinel/docker-entrypoint.sh

# [权限加固] 确保所有脚本可执行
RUN chmod +x /opt/ip_sentinel/core/*.sh \
    && chmod +x /opt/ip_sentinel/docker-entrypoint.sh

# [数据卷声明] 日志持久化存储
VOLUME ["/opt/ip_sentinel/logs"]

# [端口声明] Webhook 监听端口
EXPOSE 9527

WORKDIR /opt/ip_sentinel

ENTRYPOINT ["/opt/ip_sentinel/docker-entrypoint.sh"]
