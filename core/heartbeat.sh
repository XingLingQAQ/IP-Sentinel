#!/bin/bash

# ==========================================================
# 脚本名称: heartbeat.sh
# 核心功能: 周期性心跳上报，向 Master 司令部发送 keepalive 信号与系统状态
# 执行频率: 每 10 分钟 (由 cron/systemd timer 调度)
# ==========================================================

INSTALL_DIR="/opt/ip_sentinel"
CONFIG_FILE="${INSTALL_DIR}/config.conf"
LOG_FILE="${INSTALL_DIR}/logs/sentinel.log"
LOCK_FILE="${INSTALL_DIR}/core/.heartbeat_lock"

# --- [基础自检] 配置档缺失则静默退出 ---
if [ ! -f "$CONFIG_FILE" ]; then
    exit 0
fi
source "$CONFIG_FILE"

# --- [向下兼容] 若 MASTER_WEBHOOK_URL 未配置或为空，静默退出 ---
if [ -z "$MASTER_WEBHOOK_URL" ]; then
    exit 0
fi

# ==========================================================
# [防并发] PID 锁机制，避免多实例重复上报
# ==========================================================
if [ -f "$LOCK_FILE" ]; then
    OLD_PID=$(cat "$LOCK_FILE" 2>/dev/null)
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        # 另一个实例正在运行，静默退出
        exit 0
    fi
    # 旧进程已死，清理残留锁
    rm -f "$LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

# ==========================================================
# [数据采集] 收集节点运行态数据
# ==========================================================
TIMESTAMP=$(date +%s)

# 节点身份信息 (从配置中读取，不做实时探测)
HB_NODE_NAME="${NODE_NAME:-unknown}"
HB_NODE_ALIAS="${NODE_ALIAS:-$HB_NODE_NAME}"
HB_AGENT_VERSION="${AGENT_VERSION:-unknown}"
HB_PUBLIC_IP="${PUBLIC_IP:-unknown}"
HB_AGENT_PORT="${AGENT_PORT:-9527}"
HB_REGION_CODE="${REGION_CODE:-unknown}"

# 系统运行状态
if [ -f /proc/uptime ]; then
    HB_UPTIME=$(awk '{printf "%.0f", $1}' /proc/uptime)
elif command -v uptime >/dev/null 2>&1; then
    HB_UPTIME=$(uptime -s 2>/dev/null | xargs -I{} date -d {} +%s 2>/dev/null)
    if [ -n "$HB_UPTIME" ]; then
        HB_UPTIME=$((TIMESTAMP - HB_UPTIME))
    else
        HB_UPTIME="0"
    fi
else
    HB_UPTIME="0"
fi

# 负载均值
if [ -f /proc/loadavg ]; then
    HB_LOADAVG=$(awk '{print $1","$2","$3}' /proc/loadavg)
else
    HB_LOADAVG="0,0,0"
fi

# ==========================================================
# [数据组装] 构建 JSON 载荷
# ==========================================================
JSON_BODY=$(cat <<EOJSON
{"node_name":"${HB_NODE_NAME}","node_alias":"${HB_NODE_ALIAS}","agent_version":"${HB_AGENT_VERSION}","public_ip":"${HB_PUBLIC_IP}","agent_port":"${HB_AGENT_PORT}","region_code":"${HB_REGION_CODE}","timestamp":${TIMESTAMP},"uptime":${HB_UPTIME},"load_avg":"${HB_LOADAVG}"}
EOJSON
)
# 移除可能的换行符
JSON_BODY=$(echo "$JSON_BODY" | tr -d '\n')

# ==========================================================
# [安全签名] HMAC-SHA256 签名 (PSK = CHAT_ID)
# ==========================================================
SIGN_PAYLOAD="${JSON_BODY}:${TIMESTAMP}"
SIGNATURE=$(echo -n "$SIGN_PAYLOAD" | openssl dgst -sha256 -hmac "$CHAT_ID" | awk '{print $NF}')

# ==========================================================
# [心跳发射] POST 到 Master /heartbeat 端点
# ==========================================================
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    --connect-timeout 5 -m 10 \
    -X POST "${MASTER_WEBHOOK_URL}/heartbeat" \
    -H "Content-Type: application/json" \
    -H "X-Signature: ${SIGNATURE}" \
    -H "X-Timestamp: ${TIMESTAMP}" \
    -H "X-Chat-Id: ${CHAT_ID}" \
    -d "$JSON_BODY" 2>/dev/null)

# ==========================================================
# [结果处理] 失败时记录单行警告，成功时静默
# ==========================================================
if [ "$HTTP_CODE" != "200" ] && [ "$HTTP_CODE" != "201" ]; then
    mkdir -p "$(dirname "$LOG_FILE")"
    echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] [v${AGENT_VERSION:-N/A}] [WARN ] [Heartbeat] 心跳上报失败 (HTTP ${HTTP_CODE:-timeout}), Master: ${MASTER_WEBHOOK_URL}/heartbeat" >> "$LOG_FILE"
fi

exit 0
