#!/bin/bash

# ==========================================================
# 脚本名称: docker-entrypoint.sh (Agent)
# 核心功能: 容器启动入口，初始化配置与定时任务，前台运行 Webhook 守护进程
# ==========================================================

set -e

INSTALL_DIR="/opt/ip_sentinel"
CONFIG_FILE="${INSTALL_DIR}/config.conf"
LOG_FILE="${INSTALL_DIR}/logs/sentinel.log"

# ----------------------------------------------------------
# [信号处理] 优雅终止，确保 cron 与子进程正常退出
# ----------------------------------------------------------
cleanup() {
    echo "[Docker] 收到终止信号，正在关闭边缘节点..."
    kill -TERM "$DAEMON_PID" 2>/dev/null
    service cron stop 2>/dev/null || true
    wait "$DAEMON_PID" 2>/dev/null
    exit 0
}
trap cleanup SIGTERM SIGINT

# ----------------------------------------------------------
# [配置生成] 从环境变量生成 config.conf (若未挂载)
# ----------------------------------------------------------
if [ ! -f "$CONFIG_FILE" ]; then
    echo "[Docker] 未检测到配置文件，正在从环境变量生成..."

    AGENT_VERSION="${AGENT_VERSION:-4.1.6}"
    REGION_CODE="${REGION_CODE:-US}"
    CITY_ID="${CITY_ID:-LosAngeles}"
    STATE_ID="${STATE_ID:-CA}"
    COUNTRY_ID="${COUNTRY_ID:-US}"
    PUBLIC_IP="${PUBLIC_IP:-}"
    AGENT_PORT="${AGENT_PORT:-9527}"
    NODE_ALIAS="${NODE_ALIAS:-docker-agent}"
    ENABLE_GOOGLE="${ENABLE_GOOGLE:-true}"
    ENABLE_TRUST="${ENABLE_TRUST:-true}"
    ENABLE_OTA="${ENABLE_OTA:-false}"
    TG_TOKEN="${TG_TOKEN:-}"
    CHAT_ID="${CHAT_ID:-}"
    IP_PREF="${IP_PREF:-4}"
    BIND_IP="${BIND_IP:-}"

    # [身份锚定] 生成节点主键
    if [ -z "$PUBLIC_IP" ]; then
        PUBLIC_IP=$(curl -4 -s -m 5 api.ip.sb/ip 2>/dev/null | tr -d '[:space:]' || echo "127.0.0.1")
    fi
    IP_HASH=$(echo "${PUBLIC_IP}" | md5sum | cut -c 1-4 | tr 'a-z' 'A-Z')
    NODE_NAME="$(hostname | tr -cd 'a-zA-Z0-9' | cut -c 1-10)-${IP_HASH}"

    # [地区规则] 加载对应城市的地理配置
    REGION_JSON="${INSTALL_DIR}/data/regions/${COUNTRY_ID}/${STATE_ID}/${CITY_ID}.json"
    if [ -f "$REGION_JSON" ]; then
        REGION_NAME=$(jq -r '.region_name // "Unknown"' "$REGION_JSON")
        BASE_LAT=$(jq -r '.google_module.base_lat // "34.0522"' "$REGION_JSON")
        BASE_LON=$(jq -r '.google_module.base_lon // "-118.2437"' "$REGION_JSON")
        LANG_PARAMS=$(jq -r '.google_module.lang_params // "hl=en&gl=us"' "$REGION_JSON")
        VALID_URL_SUFFIX=$(jq -r '.google_module.valid_url_suffix // ".com"' "$REGION_JSON")
    else
        REGION_NAME="Unknown"
        BASE_LAT="34.0522"
        BASE_LON="-118.2437"
        LANG_PARAMS="hl=en&gl=us"
        VALID_URL_SUFFIX=".com"
    fi

    # [TG API 链路] 根据 Token 确定 API 端点
    if [ "$TG_TOKEN" = "OFFICIAL_GATEWAY_MODE" ]; then
        TG_API_URL="https://omni-gateway.samanthaestime296.workers.dev"
    elif [ -n "$TG_TOKEN" ]; then
        TG_API_URL="https://api.telegram.org/bot${TG_TOKEN}/sendMessage"
    else
        TG_API_URL=""
    fi

    cat > "$CONFIG_FILE" <<EOF
# IP-Sentinel 容器化配置 (自动生成)
AGENT_VERSION="$AGENT_VERSION"
REGION_CODE="$REGION_CODE"
REGION_NAME="$REGION_NAME"
BASE_LAT="$BASE_LAT"
BASE_LON="$BASE_LON"
LANG_PARAMS="$LANG_PARAMS"
VALID_URL_SUFFIX="$VALID_URL_SUFFIX"

# 模块开关状态
ENABLE_GOOGLE="$ENABLE_GOOGLE"
ENABLE_TRUST="$ENABLE_TRUST"

TG_TOKEN="$TG_TOKEN"
TG_API_URL="$TG_API_URL"
CHAT_ID="$CHAT_ID"
AGENT_PORT="$AGENT_PORT"
INSTALL_DIR="$INSTALL_DIR"
LOG_FILE="$LOG_FILE"

IP_PREF="$IP_PREF"
PUBLIC_IP="$PUBLIC_IP"
BIND_IP="$BIND_IP"

NODE_NAME="$NODE_NAME"
NODE_ALIAS="$NODE_ALIAS"

ENABLE_OTA="$ENABLE_OTA"
EOF
    chmod 600 "$CONFIG_FILE"
    echo "[Docker] 配置文件已生成: $CONFIG_FILE"
fi

# ----------------------------------------------------------
# [定时任务] 注入 crontab 条目 (替代 systemd timer)
# ----------------------------------------------------------
echo "[Docker] 正在配置定时任务调度..."

# 构建 crontab 内容: runner.sh 每20分钟, updater.sh 每日一次
CRON_CONTENT="*/20 * * * * /bin/bash ${INSTALL_DIR}/core/runner.sh >> ${LOG_FILE} 2>&1
0 4 * * * /bin/bash ${INSTALL_DIR}/core/updater.sh >> ${LOG_FILE} 2>&1
"

echo "$CRON_CONTENT" | crontab -

# 启动 cron 守护进程
service cron start
echo "[Docker] 定时任务已注入并启动 cron 守护进程。"

# ----------------------------------------------------------
# [引擎启动] 前台运行 agent_daemon.sh Webhook 监听服务
# ----------------------------------------------------------
echo "[Docker] 正在启动 IP-Sentinel Agent 边缘节点..."
bash "${INSTALL_DIR}/core/agent_daemon.sh" &
DAEMON_PID=$!

wait "$DAEMON_PID"
