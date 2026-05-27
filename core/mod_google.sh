#!/bin/bash

# ==========================================================
# 脚本名称: mod_google.sh (V4.1.1 工业级行为学重构排雷版)
# 核心功能: 
# 1. 数组级安全参数绑定 & curl 退出码精细捕获
# 2. UA 平台分离，构建平台专属行为矩阵
# 3. 引入 70% 概率动态 Referer 链 (业务域物理隔离)
# 4. 符合泊松分布(Poisson)的非均匀真实人类阅读停留时长
# ==========================================================

MODULE_NAME="Google"
CONFIG_FILE="/opt/ip_sentinel/config.conf"

# 1. 加载冷数据配置
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
else
    echo "配置文件丢失！退出执行。"
    exit 1
fi

# [V4.1.1 修复] 环境变量兜底保护，防配置丢失导致 URL 畸形
GOOGLE_BASE_URL="${GOOGLE_BASE_URL:-https://www.google.com}"

# 容错机制：如果父进程没有传递 log 函数，则本地定义一个作为 fallback
if ! type log >/dev/null 2>&1; then
    log() {
        # 提取当前配置中的版本锚点
        local local_ver="${AGENT_VERSION:-未知}"
        
        # 保证日志目录存在
        mkdir -p "${INSTALL_DIR}/logs"
    
        # 日志格式注入 [版本号] 追踪标识
        local core_msg=$(printf "[v%-5s] [%-5s] [%-7s] [%s] %s" "$local_ver" "$2" "$1" "$REGION_CODE" "$3")
        # [时区对齐] 强制无视本地时区，以绝对 UTC 时间写入日志
        echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] $core_msg" >> "${INSTALL_DIR}/logs/sentinel.log"

        # 强制推送到 Systemd Journal
        if command -v logger >/dev/null 2>&1; then
            logger -t ip-sentinel "$core_msg"
        else
            echo "$core_msg"
        fi
    }
fi

log "$MODULE_NAME" "START" "========== 唤醒网络模拟器 [区域: $REGION_NAME] =========="

# --- [V4.1.1 强制依赖检测 (防系统环境残缺)] ---
MISSING_DEPS=()
for dep in jq curl awk flock; do
    command -v "$dep" >/dev/null 2>&1 || MISSING_DEPS+=("$dep")
done
if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    log "$MODULE_NAME" "ERROR" "系统残缺，缺少必备组件: ${MISSING_DEPS[*]}。拒绝执行。"
    exit 1
fi

# 2. 动态加载热数据 (设备指纹池 和 专属搜索词库)
UA_FILE="${INSTALL_DIR}/data/user_agents.txt"
KW_FILE="${INSTALL_DIR}/data/keywords/kw_${REGION_CODE}.txt"

if [ ! -f "$UA_FILE" ] || [ ! -f "$KW_FILE" ]; then
    log "$MODULE_NAME" "ERROR" "热数据缺失，请检查 data 目录。放弃本次执行。"
    exit 1
fi

# 将文本按行读取到数组中 (并自动过滤空行)
mapfile -t UA_POOL < <(grep -v '^$' "$UA_FILE")
mapfile -t KEYWORDS < <(grep -v '^$' "$KW_FILE")

if [ ${#KEYWORDS[@]} -eq 0 ]; then
    log "$MODULE_NAME" "ERROR" "关键词库为空，终止执行。"
    exit 1
fi

# --- [工具函数] ---
get_random_coord() {
    local base=$1
    local range=$2 
    local offset=$(awk "BEGIN {print ( ( ($RANDOM % ($range * 2)) - $range ) / 10000 )}")
    awk "BEGIN {print ($base + $offset)}"
}

# --- [环境初始化] ---
CURRENT_IP="${PUBLIC_IP:-${BIND_IP:-Unknown}}"

# -----------------------------------------------------------
# [V3.1.5] 哈希锚定法 (Hash-Seeded Persona) 
# 利用 IP 算力固定 3 个永久化专属指纹，破除僵尸网络同质化特征
# -----------------------------------------------------------
TOTAL_UA=${#UA_POOL[@]}
if [ "$TOTAL_UA" -gt 0 ]; then
    SEED=$(echo -n "$CURRENT_IP" | cksum | awk '{print $1}')
    IDX1=$(( SEED % TOTAL_UA ))
    IDX2=$(( (SEED * 17) % TOTAL_UA ))
    IDX3=$(( (SEED * 31) % TOTAL_UA ))
    MY_UA_POOL=("${UA_POOL[$IDX1]}" "${UA_POOL[$IDX2]}" "${UA_POOL[$IDX3]}")
    SESSION_UA=${MY_UA_POOL[$RANDOM % 3]}
else
    SESSION_UA="Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
fi

# -----------------------------------------------------------
# [V4.1.1 平台身份提取器 (Persona Mapper)]
# -----------------------------------------------------------
UA_PLATFORM="windows"
if [[ "$SESSION_UA" == *"Android"* ]]; then
    UA_PLATFORM="android"
elif [[ "$SESSION_UA" == *"iPhone"* ]] || [[ "$SESSION_UA" == *"iPad"* ]]; then
    UA_PLATFORM="ios"
elif [[ "$SESSION_UA" == *"Macintosh"* ]]; then
    UA_PLATFORM="macos"
elif [[ "$SESSION_UA" == *"Linux"* ]]; then
    UA_PLATFORM="linux"
fi

SESSION_BASE_LAT=$(get_random_coord $BASE_LAT 270)
SESSION_BASE_LON=$(get_random_coord $BASE_LON 270)
TOTAL_ACTIONS=$((5 + RANDOM % 4))

log "$MODULE_NAME" "INFO " "指纹锁定: ${SESSION_UA:0:45}..."
log "$MODULE_NAME" "INFO " "平台推断: [$UA_PLATFORM] | 驻留坐标: $SESSION_BASE_LAT, $SESSION_BASE_LON"

# -----------------------------------------------------------
# [V4.1.1] 持久化 Cookie 身份库
# -----------------------------------------------------------
COOKIE_DIR="${INSTALL_DIR}/data/cookies"
mkdir -p "$COOKIE_DIR"
NODE_HASH=$(echo -n "$CURRENT_IP" | cksum | awk '{print $1}')
COOKIE_FILE="${COOKIE_DIR}/google_${NODE_HASH}.txt"

LOCK_FILE="${COOKIE_FILE}.lock"
exec 200>"$LOCK_FILE"
flock -n 200 || {
    log "$MODULE_NAME" "WARN " "检测到已有 Google 会话运行，跳过本轮。"
    exit 0
}

# -----------------------------------------------------------
# [V4.1.1 数组级安全参数绑定]
# 彻底消除 Shell Word Splitting（拆词）风险
# -----------------------------------------------------------
CURL_BIND_OPT=()
DYNAMIC_IP_PREF="-${IP_PREF:-4}" 

if [[ -n "$BIND_IP" && "$BIND_IP" =~ ^[0-9a-fA-F:\.]+$ ]]; then
    RAW_BIND_IP=$(echo "$BIND_IP" | tr -d '[]')
    if ! ip addr show 2>/dev/null | grep -Fq "$RAW_BIND_IP"; then
        log "$MODULE_NAME" "WARN " "检测到配置的出口 IP ($RAW_BIND_IP) 已丢失，自动降级为系统默认路由出网！"
    else
        CURL_BIND_OPT+=(--interface "$BIND_IP")
        if [[ "$BIND_IP" == *":"* ]]; then
            DYNAMIC_IP_PREF="-6"
        elif [[ "$BIND_IP" == *"."* ]]; then
            DYNAMIC_IP_PREF="-4"
        fi
    fi
fi

# -----------------------------------------------------------
# [V4.1.1] 生物节律系统
# -----------------------------------------------------------
LOCAL_HOUR=$(date +%H)
if [ "$LOCAL_HOUR" -ge 1 ] && [ "$LOCAL_HOUR" -le 6 ]; then
    if [ $((RANDOM % 100)) -lt 70 ]; then
        log "$MODULE_NAME" "INFO " "🌙 夜间生物节律触发，本轮进入深度睡眠。"
        exit 0
    fi
fi

# ==========================================================
# [V4.1.1] 底层静态 Curl 参数提取 (剥离 -f 陷阱)
# 抛弃 -f (fail silently) 才能精准捕获 HTTP 403 / 429 风控拦截
# ==========================================================
BASE_CURL=(curl -sSL --connect-timeout 10 -m 25)
BASE_CURL+=("$DYNAMIC_IP_PREF")
BASE_CURL+=(--http2)
if [ ${#CURL_BIND_OPT[@]} -gt 0 ]; then
    BASE_CURL+=("${CURL_BIND_OPT[@]}")
fi
BASE_CURL+=(-b "$COOKIE_FILE" -c "$COOKIE_FILE")
BASE_CURL+=(-A "$SESSION_UA")
BASE_CURL+=(-H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8")
BASE_CURL+=(-H "Accept-Language: ${LANG_ACCEPT}")
BASE_CURL+=(-H "Upgrade-Insecure-Requests: 1")
BASE_CURL+=(-H "DNT: 1")
if [ -n "$GEO_HEADER" ]; then 
    BASE_CURL+=(-H "$GEO_HEADER")
fi

# [V4.1.1] 业务域 Referer 物理隔离 (防穿帮)
REF_SEARCH=""
REF_NEWS=""
REF_MAPS=""
REF_ECO=""

LOW_RISK_ECO=(
    "https://about.google/"
    "https://safety.google/"
    "https://policies.google.com/privacy?hl=${LANG_ACCEPT%%,*}"
    "https://support.google.com/?hl=${LANG_ACCEPT%%,*}"
)

# --- [行为循环模拟] ---
for ((i=1; i<=TOTAL_ACTIONS; i++)); do
    ACTION_LAT=$(get_random_coord $SESSION_BASE_LAT 1)
    ACTION_LON=$(get_random_coord $SESSION_BASE_LON 1)
    
    RAND_KEY=${KEYWORDS[$RANDOM % ${#KEYWORDS[@]}]}
    
    # [V4.1.1 修复] 切回最可靠的原生 jq uri，完美支持 UTF-8 中文编码
    ENCODED_KEY=$(printf '%s' "$RAND_KEY" | jq -sRr @uri)
    [ -z "$ENCODED_KEY" ] && ENCODED_KEY="google"

    ACTION_DICE=$((RANDOM % 100))
    TARGET_URL=""
    ACTION_LOG=""

    # [V4.1.1] 基于平台的动态行为矩阵选择 (杜绝 iOS 访问 Android 探针)
    if [ "$UA_PLATFORM" == "android" ]; then
        if [ $ACTION_DICE -lt 25 ]; then
            TARGET_URL="${GOOGLE_BASE_URL}/search?q=${ENCODED_KEY}&${LANG_PARAMS}"
            ACTION_LOG="Search "
        elif [ $ACTION_DICE -lt 55 ]; then
            TARGET_URL="https://news.google.com/home?${LANG_PARAMS}"
            ACTION_LOG="News   "
        elif [ $ACTION_DICE -lt 85 ]; then
            TARGET_URL="https://www.google.com/maps?q=${ENCODED_KEY}&ll=${ACTION_LAT},${ACTION_LON}&z=17"
            ACTION_LOG="Maps   "
        else
            TARGET_URL="https://connectivitycheck.gstatic.com/generate_204"
            ACTION_LOG="NetTest"
        fi
    elif [ "$UA_PLATFORM" == "ios" ] || [ "$UA_PLATFORM" == "macos" ]; then
        if [ $ACTION_DICE -lt 30 ]; then
            TARGET_URL="${GOOGLE_BASE_URL}/search?q=${ENCODED_KEY}&${LANG_PARAMS}"
            ACTION_LOG="Search "
        elif [ $ACTION_DICE -lt 65 ]; then
            TARGET_URL="https://news.google.com/home?${LANG_PARAMS}"
            ACTION_LOG="News   "
        elif [ $ACTION_DICE -lt 90 ]; then
            TARGET_URL="https://www.google.com/maps?q=${ENCODED_KEY}&ll=${ACTION_LAT},${ACTION_LON}&z=17"
            ACTION_LOG="Maps   "
        else
            TARGET_URL="https://captive.apple.com/hotspot-detect.html"
            ACTION_LOG="NetTest"
        fi
    else
        # Windows / Linux 专属行为矩阵
        if [ $ACTION_DICE -lt 20 ]; then
            TARGET_URL="${GOOGLE_BASE_URL}/search?q=${ENCODED_KEY}&${LANG_PARAMS}"
            ACTION_LOG="Search "
        elif [ $ACTION_DICE -lt 60 ]; then
            TARGET_URL="https://news.google.com/home?${LANG_PARAMS}"
            ACTION_LOG="News   "
        elif [ $ACTION_DICE -lt 80 ]; then
            TARGET_URL="${LOW_RISK_ECO[$((RANDOM % ${#LOW_RISK_ECO[@]}))]}"
            ACTION_LOG="EcoRoam"
        else
            TARGET_URL="https://www.google.com/maps?q=${ENCODED_KEY}&ll=${ACTION_LAT},${ACTION_LON}&z=17"
            ACTION_LOG="Maps   "
        fi
    fi

    # [V4.1.1] Referer 业务域隔离判断
    CTX_REF=""
    case "$ACTION_LOG" in
        "Search "*) CTX_REF="$REF_SEARCH" ;;
        "News "*)   CTX_REF="$REF_NEWS" ;;
        "Maps "*)   CTX_REF="$REF_MAPS" ;;
        "EcoRoam"*) CTX_REF="$REF_ECO" ;;
    esac

    # 动态载入 Referer (70% 概率)
    CURL_EXEC=("${BASE_CURL[@]}")
    if [ -n "$CTX_REF" ] && [ $((RANDOM % 100)) -lt 70 ]; then
        CURL_EXEC+=(-H "Referer: $CTX_REF")
    fi

    # 执行命令并捕获细分错误码
    HTTP_CODE=$("${CURL_EXEC[@]}" -o /dev/null -w "%{http_code}" "$TARGET_URL")
    CURL_EXIT=$?

    # [V4.1.1] 精确分离 Curl 网络错误与 HTTP 协议层拦截
    if [ $CURL_EXIT -ne 0 ]; then
        case $CURL_EXIT in
            6)  CURL_ERR_CODE="ERR_6_DNS" ;;
            7)  CURL_ERR_CODE="ERR_7_CONN" ;;
            28) CURL_ERR_CODE="ERR_28_TIMEOUT" ;;
            35) CURL_ERR_CODE="ERR_35_TLS" ;;
            56) CURL_ERR_CODE="ERR_56_RESET" ;;
            *)  CURL_ERR_CODE="ERR_${CURL_EXIT}" ;;
        esac
        log "$MODULE_NAME" "WARN " "❌ ${ACTION_LOG} Curl底层故障 | Code: $CURL_ERR_CODE | T: ${TARGET_URL:0:35}"
        
        # 请求失败，清空当前业务链的 Referer
        case "$ACTION_LOG" in
            "Search "*) REF_SEARCH="" ;;
            "News "*)   REF_NEWS="" ;;
            "Maps "*)   REF_MAPS="" ;;
            "EcoRoam"*) REF_ECO="" ;;
        esac
    else
        # Curl 连通了，评估 HTTP 状态码
        if [[ "$HTTP_CODE" =~ ^[23] ]]; then
            log "$MODULE_NAME" "EXEC " "✅ ${ACTION_LOG} success | Code: $HTTP_CODE | T: ${TARGET_URL:0:35}"
            # 更新业务专属跳板 (网络测试页不作为 Referer)
            case "$ACTION_LOG" in
                "Search "*) REF_SEARCH="$TARGET_URL" ;;
                "News "*)   REF_NEWS="$TARGET_URL" ;;
                "Maps "*)   REF_MAPS="$TARGET_URL" ;;
                "EcoRoam"*) REF_ECO="$TARGET_URL" ;;
            esac
        else
            log "$MODULE_NAME" "WARN " "❌ ${ACTION_LOG} 疑似遭风控拒绝 | Code: $HTTP_CODE | T: ${TARGET_URL:0:35}"
        fi
    fi
    
    # [V4.1.1] 泊松长尾分布，模拟人类真实停留
    if [ $i -lt $TOTAL_ACTIONS ]; then
        SLEEP_DICE=$((RANDOM % 100))
        if [ $SLEEP_DICE -lt 45 ]; then
            SLEEP_TIME=$((8 + RANDOM % 13))    # 8 - 20s (45%)
        elif [ $SLEEP_DICE -lt 80 ]; then
            SLEEP_TIME=$((20 + RANDOM % 41))   # 20 - 60s (35%)
        elif [ $SLEEP_DICE -lt 95 ]; then
            SLEEP_TIME=$((60 + RANDOM % 121))  # 60 - 180s (15%)
        else
            SLEEP_TIME=$((180 + RANDOM % 300)) # 180 - 480s (5%)
        fi
        log "$MODULE_NAME" "WAIT " "模拟真实浏览，停留 ${SLEEP_TIME}s..."
        sleep $SLEEP_TIME
    fi
done

# --- [结果纠偏自检 (V4.1.1 终极三核雷达: URL跳转 + Premium + Music)] ---
log "$MODULE_NAME" "INFO " "启动三核交叉验证 (URL跳转 + YT Premium + YT Music) 穿透获取 GeoIP..."

# 核心 1: 传统 URL 跳转探测 (数组安全传参 + 剥离 -f)
JUMP_HDR=$(curl -sI -m 10 --http2 \
    $DYNAMIC_IP_PREF \
    ${CURL_BIND_OPT[@]:+"${CURL_BIND_OPT[@]}"} \
    -b "$COOKIE_FILE" -c "$COOKIE_FILE" \
    -A "$SESSION_UA" \
    -H "Accept-Language: ${LANG_ACCEPT}" \
    "http://www.google.com/")
JUMP_LOC=$(echo "$JUMP_HDR" | grep -i "^location:" | tr -d '\r\n')
JUMP_GL=""

if [ -z "$JUMP_LOC" ]; then
    JUMP_GL="US"
elif [[ "$JUMP_LOC" == *".google.cn"* ]] || [[ "$JUMP_LOC" == *"gl=CN"* ]]; then
    JUMP_GL="CN"
elif [[ "$JUMP_LOC" == *"gl="* ]]; then
    JUMP_GL=$(echo "$JUMP_LOC" | grep -o 'gl=[A-Za-z]\{2\}' | head -n 1 | cut -d'=' -f2 | tr 'a-z' 'A-Z')
else
    JUMP_DOMAIN=$(echo "$JUMP_LOC" | grep -o 'google\.[a-z\.]*' | head -n 1 | sed 's/google\.//')
    case "$JUMP_DOMAIN" in
        "com") JUMP_GL="US" ;; "com.hk") JUMP_GL="HK" ;; "com.tw") JUMP_GL="TW" ;;
        "co.jp") JUMP_GL="JP" ;; "co.uk") JUMP_GL="GB" ;; "co.kr") JUMP_GL="KR" ;;
        "co.in") JUMP_GL="IN" ;; "co.id") JUMP_GL="ID" ;; "co.th") JUMP_GL="TH" ;;
        "com.sg") JUMP_GL="SG" ;; "com.my") JUMP_GL="MY" ;; "com.au") JUMP_GL="AU" ;;
        "com.br") JUMP_GL="BR" ;; "com.mx") JUMP_GL="MX" ;; "com.ar") JUMP_GL="AR" ;;
        "co.za") JUMP_GL="ZA" ;; "cn") JUMP_GL="CN" ;; "") JUMP_GL="" ;;
        *) 
            LAST_EXT=$(echo "$JUMP_DOMAIN" | awk -F'.' '{print $NF}' | tr 'a-z' 'A-Z')
            if [ ${#LAST_EXT} -eq 2 ]; then JUMP_GL="$LAST_EXT"; else JUMP_GL="US"; fi
            ;;
    esac
fi

# 核心 2: YouTube Premium 探测
YT_PR_GL=""
YT_PR_HTML=$(curl -sSL -m 10 --http2 \
    $DYNAMIC_IP_PREF \
    ${CURL_BIND_OPT[@]:+"${CURL_BIND_OPT[@]}"} \
    -b "$COOKIE_FILE" -c "$COOKIE_FILE" \
    -A "$SESSION_UA" \
    -H "Accept-Language: ${LANG_ACCEPT}" \
    "https://www.youtube.com/premium")
if [[ "$YT_PR_HTML" == *"www.google.cn"* ]]; then
    YT_PR_GL="CN"
else
    YT_PR_GL=$(echo "$YT_PR_HTML" | grep -o '"contentRegion":"[A-Za-z]\{2\}"' | head -n 1 | cut -d'"' -f4 | tr 'a-z' 'A-Z')
    [ -z "$YT_PR_GL" ] && YT_PR_GL=$(echo "$YT_PR_HTML" | grep -o '"countryCode":"[A-Za-z]\{2\}"' | head -n 1 | cut -d'"' -f4 | tr 'a-z' 'A-Z')
    [ -z "$YT_PR_GL" ] && YT_PR_GL=$(echo "$YT_PR_HTML" | grep -o '"INNERTUBE_CONTEXT_GL":"[A-Za-z]\{2\}"' | head -n 1 | cut -d'"' -f4 | tr 'a-z' 'A-Z')
fi

# 核心 3: YouTube Music 探测
YT_MU_GL=""
YT_MU_HTML=$(curl -sSL -m 10 --http2 \
    $DYNAMIC_IP_PREF \
    ${CURL_BIND_OPT[@]:+"${CURL_BIND_OPT[@]}"} \
    -b "$COOKIE_FILE" -c "$COOKIE_FILE" \
    -A "$SESSION_UA" \
    -H "Accept-Language: ${LANG_ACCEPT}" \
    "https://music.youtube.com/")
if [[ "$YT_MU_HTML" == *"www.google.cn"* ]]; then
    YT_MU_GL="CN"
else
    YT_MU_GL=$(echo "$YT_MU_HTML" | grep -o '"INNERTUBE_CONTEXT_GL":"[A-Za-z]\{2\}"' | head -n 1 | cut -d'"' -f4 | tr 'a-z' 'A-Z')
    [ -z "$YT_MU_GL" ] && YT_MU_GL=$(echo "$YT_MU_HTML" | grep -o '"countryCode":"[A-Za-z]\{2\}"' | head -n 1 | cut -d'"' -f4 | tr 'a-z' 'A-Z')
    [ -z "$YT_MU_GL" ] && YT_MU_GL=$(echo "$YT_MU_HTML" | grep -o '"GL":"[A-Za-z]\{2\}"' | head -n 1 | cut -d'"' -f4 | tr 'a-z' 'A-Z')
fi

# [基准对齐] 提取配置大区 (兼容州级穿透)，并修正英国的 ISO 代码
TARGET_CC="${REGION_CODE%%-*}"
[ "$TARGET_CC" == "UK" ] && TARGET_CC="GB"

# --- 终极审判逻辑 ---
IS_CN=0
VALID_PROBES=0
for val in "$JUMP_GL" "$YT_PR_GL" "$YT_MU_GL"; do
    if [ -n "$val" ]; then
        ((VALID_PROBES++))
        [ "$val" == "CN" ] && IS_CN=1
    fi
done

if [ $VALID_PROBES -eq 0 ]; then
    STATUS="🚨 探针失效 (三核全部熔断，可能遭严重风控拦截)"
elif [ $IS_CN -eq 1 ]; then
    STATUS="❌ 严重高危！三核雷达判定 IP 已被中国大陆锁定 (送中)！"
else
    YT_MATCH=0
    [ "$YT_PR_GL" == "$TARGET_CC" ] && YT_MATCH=1
    [ "$YT_MU_GL" == "$TARGET_CC" ] && YT_MATCH=1

    if [ $YT_MATCH -eq 1 ]; then
        if [ -n "$JUMP_GL" ] && [ "$JUMP_GL" != "$TARGET_CC" ]; then
            STATUS="✅ 目标区域达成 (YT主导成功, Jump副雷达漂移至 ${JUMP_GL}) | Prem: ${YT_PR_GL:-无} | Music: ${YT_MU_GL:-无}"
        else
            STATUS="✅ 目标区域达成 (Jump: ${JUMP_GL:-无} | Prem: ${YT_PR_GL:-无} | Music: ${YT_MU_GL:-无})"
        fi
    else
        STATUS="⚠️ 区域发生漂移！目标 $TARGET_CC，实际 (Jump: ${JUMP_GL:-无} | Prem: ${YT_PR_GL:-无} | Music: ${YT_MU_GL:-无})"
    fi
fi

log "$MODULE_NAME" "SCORE" "自检结论: $STATUS"

# [V4.1.1] 定期清理 Cookie 垃圾防爆栈 (清理超过 14 天的 Cookie)
find "$COOKIE_DIR" -type f -name "google_*.txt" -mtime +14 -delete 2>/dev/null || true

log "$MODULE_NAME" "END  " "========== 会话结束，释放进程 =========="