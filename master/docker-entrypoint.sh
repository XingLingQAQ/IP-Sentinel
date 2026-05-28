#!/bin/bash

# ==========================================================
# 脚本名称: docker-entrypoint.sh (Master)
# 核心功能: 容器启动入口，初始化数据库与配置，前台运行中枢引擎
# ==========================================================

set -e

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

    if [ -z "$TG_TOKEN" ]; then
        echo "[Docker] 致命错误: 环境变量 TG_TOKEN 未设置！"
        echo "请通过 docker run -e TG_TOKEN=xxx 或 docker-compose 环境变量传入。"
        exit 1
    fi

    MASTER_VERSION="${MASTER_VERSION:-4.1.1}"
    IS_OFFICIAL_GATEWAY="${IS_OFFICIAL_GATEWAY:-false}"
    ENABLE_MASTER_OTA="${ENABLE_MASTER_OTA:-false}"

    cat > "$CONF_FILE" <<EOF
# IP-Sentinel Master 容器化配置 (自动生成)
MASTER_VERSION="$MASTER_VERSION"
TG_TOKEN="$TG_TOKEN"
DB_FILE="$DB_FILE"
MASTER_DIR="$MASTER_DIR"
IS_OFFICIAL_GATEWAY="$IS_OFFICIAL_GATEWAY"
ENABLE_MASTER_OTA="$ENABLE_MASTER_OTA"
EOF
    chmod 600 "$CONF_FILE"
    echo "[Docker] 配置文件已生成: $CONF_FILE"
fi

# ----------------------------------------------------------
# [引擎启动] 前台运行 tg_master.sh 长轮询服务
# ----------------------------------------------------------
echo "[Docker] 正在启动 IP-Sentinel Master 控制中枢..."
bash "${MASTER_DIR}/tg_master.sh" &
MASTER_PID=$!

wait "$MASTER_PID"
