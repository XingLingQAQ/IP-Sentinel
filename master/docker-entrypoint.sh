#!/bin/bash

# ==========================================================
# 脚本名称: docker-entrypoint.sh (Master)
# 核心功能: 容器启动入口，初始化数据库与配置，注册 Webhook，前台运行中枢引擎
# ==========================================================

set -e
# [容灾覆盖] curl/网络失败不应阻止主服务启动
set +e

MASTER_DIR="/opt/ip_sentinel_master"
DB_FILE="${MASTER_DIR}/data/sentinel.db"
CONF_FILE="${MASTER_DIR}/master.conf"

# ----------------------------------------------------------
# [信号处理] 优雅终止，确保子进程正常退出
# ----------------------------------------------------------
cleanup() {
    echo "[Docker] 收到终止信号，正在关闭中枢引擎..."
    kill -TERM "$MASTER_PID" 2>/dev/null
    wait "$MASTER_PID" 2>/dev/null
    exit 0
}
trap cleanup SIGTERM SIGINT

# ----------------------------------------------------------
# [环境变量校验] 检查必需的环境变量
# ----------------------------------------------------------
if [ -z "$TG_TOKEN" ]; then
    echo "[Docker] 致命错误: 环境变量 TG_TOKEN 未设置！"
    echo "请通过 docker run -e TG_TOKEN=xxx 或 docker-compose 环境变量传入。"
    exit 1
fi

if [ -z "$WEBHOOK_URL" ]; then
    echo "[Docker] 致命错误: 环境变量 WEBHOOK_URL 未设置！"
    echo "请通过 docker run -e WEBHOOK_URL=https://your-domain.com 或 docker-compose 环境变量传入。"
    exit 1
fi

if [ -z "$CHAT_ID" ]; then
    echo "[Docker] 警告: 环境变量 CHAT_ID 未设置，部分功能可能受限。"
fi

# ----------------------------------------------------------
# [数据库初始化] 若 SQLite 库不存在则创建表结构基线
# ----------------------------------------------------------
if [ ! -f "$DB_FILE" ]; then
    echo "[Docker] 首次启动，正在初始化 SQLite 数据库..."
    sqlite3 "$DB_FILE" <<EOF
CREATE TABLE IF NOT EXISTS nodes (
    chat_id TEXT,
    node_name TEXT,
    agent_ip TEXT,
    agent_port TEXT,
    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    region TEXT DEFAULT 'UNKNOWN',
    node_alias TEXT,
    enable_google TEXT DEFAULT 'true',
    enable_trust TEXT DEFAULT 'true',
    enable_ota TEXT DEFAULT 'false',
    PRIMARY KEY(chat_id, node_name)
);

CREATE TABLE IF NOT EXISTS ip_trend_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_name TEXT,
    check_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    scam_score INTEGER,
    goog_status TEXT,
    nf_status TEXT,
    gpt_status TEXT
);
EOF
    chmod 600 "$DB_FILE"
    echo "[Docker] 数据库初始化完成: $DB_FILE"
fi

# ----------------------------------------------------------
# [配置生成] 从环境变量生成 master.conf (若未挂载)
# ----------------------------------------------------------
if [ ! -f "$CONF_FILE" ]; then
    echo "[Docker] 未检测到配置文件，正在从环境变量生成..."

    MASTER_VERSION="${MASTER_VERSION:-5.0.0}"
    IS_OFFICIAL_GATEWAY="${IS_OFFICIAL_GATEWAY:-false}"
    ENABLE_MASTER_OTA="${ENABLE_MASTER_OTA:-false}"

    (umask 077; cat > "$CONF_FILE" <<EOF
# IP-Sentinel Master 容器化配置 (自动生成)
MASTER_VERSION="$MASTER_VERSION"
TG_TOKEN="$TG_TOKEN"
DB_FILE="$DB_FILE"
MASTER_DIR="$MASTER_DIR"
IS_OFFICIAL_GATEWAY="$IS_OFFICIAL_GATEWAY"
ENABLE_MASTER_OTA="$ENABLE_MASTER_OTA"
WEBHOOK_URL="$WEBHOOK_URL"
CHAT_ID="${CHAT_ID:-}"
EOF
    )
    echo "[Docker] 配置文件已生成: $CONF_FILE"
fi

# ----------------------------------------------------------
# [Webhook 秘钥] 生成或使用提供的 WEBHOOK_SECRET
# ----------------------------------------------------------
if [ -z "$WEBHOOK_SECRET" ]; then
    WEBHOOK_SECRET=$(openssl rand -hex 32)
    echo "[Docker] 已自动生成 WEBHOOK_SECRET (随机 256-bit)"
fi
export WEBHOOK_SECRET

# ----------------------------------------------------------
# [引擎启动] 先启动 Python 服务，再注册 Webhook
# 必须先让服务在线，Telegram 才能验证 Webhook 端点可达
# ----------------------------------------------------------
echo "[Docker] 正在启动 IP-Sentinel Master 控制中枢 (Webhook 模式)..."

export TG_TOKEN DB_FILE MASTER_DIR MASTER_VERSION IS_OFFICIAL_GATEWAY ENABLE_MASTER_OTA WEBHOOK_URL CHAT_ID WEBHOOK_SECRET

python3 "${MASTER_DIR}/webhook_master.py" &
MASTER_PID=$!

# ----------------------------------------------------------
# [Webhook 注册] 等待 Python 服务就绪后再注册
# 最多等待 30 秒，失败后仍继续运行（服务本身正常）
# ----------------------------------------------------------
echo "[Docker] 等待 Webhook 服务就绪..."
_RETRY=0
while [ $_RETRY -lt 15 ]; do
    if curl -sf --connect-timeout 2 "http://127.0.0.1:7860/health" >/dev/null 2>&1; then
        break
    fi
    sleep 2
    _RETRY=$((_RETRY + 1))
done

echo "[Docker] 正在注册 Telegram Webhook..."
WEBHOOK_RESULT=$(curl -s --connect-timeout 10 -m 15 \
    -X POST "https://api.telegram.org/bot${TG_TOKEN}/setWebhook" \
    -d "url=${WEBHOOK_URL}/webhook" \
    -d "allowed_updates=[\"message\",\"callback_query\"]" \
    -d "secret_token=${WEBHOOK_SECRET}" 2>&1)
_CURL_CODE=$?

if [ $_CURL_CODE -ne 0 ]; then
    echo "[Docker] 警告: Webhook 注册网络错误 (curl exit ${_CURL_CODE})，服务已启动但尚未注册。"
    echo "[Docker] 容器完全就绪后可手动重试: curl -X POST https://api.telegram.org/bot\${TG_TOKEN}/setWebhook -d url=\${WEBHOOK_URL}/webhook"
elif echo "$WEBHOOK_RESULT" | grep -q '"ok":true'; then
    echo "[Docker] Webhook 注册成功: ${WEBHOOK_URL}/webhook"
else
    echo "[Docker] 警告: Webhook 注册失败: $WEBHOOK_RESULT"
fi

wait "$MASTER_PID"
