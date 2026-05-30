#!/usr/bin/env python3
"""
IP-Sentinel Master Webhook Server
Replaces tg_master.sh long-polling with a webhook-driven HTTP server.
Uses ONLY Python3 standard library - zero third-party dependencies.
"""

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import subprocess
import threading
import time
import traceback
import urllib.parse
import urllib.request
from base64 import b64encode
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

# ==========================================================
# Configuration
# ==========================================================

TG_TOKEN = os.environ.get("TG_TOKEN", "")
DB_FILE = os.environ.get("DB_FILE", "/opt/ip_sentinel_master/data/sentinel.db")
MASTER_DIR = os.environ.get("MASTER_DIR", "/opt/ip_sentinel_master")
MASTER_VERSION = os.environ.get("MASTER_VERSION", "5.0.1")
IS_OFFICIAL_GATEWAY = os.environ.get("IS_OFFICIAL_GATEWAY", "false")
ENABLE_MASTER_OTA = os.environ.get("ENABLE_MASTER_OTA", "false")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "") or secrets.token_hex(32)

REPO_RAW_URL = "https://raw.githubusercontent.com/XingLingQAQ/IP-Sentinel/main"
SERVER_PORT = 7860
MAX_BODY_SIZE = 1_048_576  # 1 MB request body limit

# Debug mode: set DEBUG=true env var to enable verbose logging
DEBUG = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")

# Anomaly alert cooldown: suppress duplicate alerts for the same node for 60 minutes
_alert_cooldowns = {}  # (chat_id, node_name) -> last_alert_timestamp
ALERT_COOLDOWN_SECONDS = 3600


def debug_log(msg):
    """Print debug message only when DEBUG mode is enabled."""
    if DEBUG:
        print(f"[DEBUG] [{time.strftime('%H:%M:%S')}] {msg}")

# ==========================================================
# Flag Mapping
# ==========================================================

FLAG_MAP = {
    "US": "🇺🇸", "JP": "🇯🇵",
    "HK": "🇭🇰", "TW": "🇹🇼",
    "SG": "🇸🇬", "UK": "🇬🇧",
    "GB": "🇬🇧", "DE": "🇩🇪",
    "FR": "🇫🇷", "NL": "🇳🇱",
    "CA": "🇨🇦", "AU": "🇦🇺",
    "KR": "🇰🇷", "IN": "🇮🇳",
    "BR": "🇧🇷", "RU": "🇷🇺",
    "CH": "🇨🇭", "SE": "🇸🇪",
    "NO": "🇳🇴", "DK": "🇩🇰",
    "FI": "🇫🇮", "IT": "🇮🇹",
    "ES": "🇪🇸", "PT": "🇵🇹",
    "IE": "🇮🇪", "PL": "🇵🇱",
    "AT": "🇦🇹", "BE": "🇧🇪",
    "TR": "🇹🇷", "ZA": "🇿🇦",
    "AE": "🇦🇪", "MY": "🇲🇾",
    "ID": "🇮🇩", "VN": "🇻🇳",
    "TH": "🇹🇭", "PH": "🇵🇭",
    "NZ": "🇳🇿", "AR": "🇦🇷",
    "CL": "🇨🇱", "MX": "🇲🇽",
    "IL": "🇮🇱", "SA": "🇸🇦",
    "EG": "🇪🇬", "NG": "🇳🇬",
    "KE": "🇰🇪", "RO": "🇷🇴",
    "BG": "🇧🇬", "CZ": "🇨🇿",
    "HU": "🇭🇺", "GR": "🇬🇷",
    "UA": "🇺🇦", "MO": "🇲🇴",
    "KH": "🇰🇭", "MM": "🇲🇲",
    "LA": "🇱🇦", "MN": "🇲🇳",
    "NP": "🇳🇵", "BD": "🇧🇩",
}


def get_flag(region_code):
    """Map region code to emoji flag."""
    if not region_code:
        return "🌐"
    base_cc = region_code.upper().split("-")[0]
    return FLAG_MAP.get(base_cc, "🌐")

# ==========================================================
# Database Helpers
# ==========================================================

_db_local = threading.local()


def get_db():
    """Get a thread-local SQLite connection with WAL mode."""
    if not hasattr(_db_local, "conn"):
        conn = sqlite3.connect(DB_FILE, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.row_factory = sqlite3.Row
        _db_local.conn = conn
    return _db_local.conn


def db_exec(sql, params=None):
    """Execute SQL and return fetchall results."""
    conn = get_db()
    try:
        if params:
            cur = conn.execute(sql, params)
        else:
            cur = conn.execute(sql)
        conn.commit()
        return cur.fetchall()
    except sqlite3.Error:
        conn.rollback()
        return []


def init_db():
    """Initialize database tables and run auto-migration."""
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")

    conn.execute("""CREATE TABLE IF NOT EXISTS nodes (
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
    );""")

    conn.execute("""CREATE TABLE IF NOT EXISTS ip_trend_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        node_name TEXT,
        check_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        scam_score INTEGER,
        goog_status TEXT,
        nf_status TEXT,
        gpt_status TEXT
    );""")

    # Auto-migration: add columns if missing (self-healing schema)
    migrations = [
        ("nodes", "region", "TEXT DEFAULT 'UNKNOWN'"),
        ("nodes", "node_alias", "TEXT"),
        ("nodes", "enable_google", "TEXT DEFAULT 'true'"),
        ("nodes", "enable_trust", "TEXT DEFAULT 'true'"),
        ("nodes", "enable_ota", "TEXT DEFAULT 'false'"),
        ("ip_trend_log", "goog_status", "TEXT DEFAULT 'Unknown'"),
        ("ip_trend_log", "gpt_status", "TEXT DEFAULT 'Unknown'"),
    ]
    for table, col, col_type in migrations:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type};")
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()



# ==========================================================
# HMAC Signature Engine
# ==========================================================


def generate_signed_url(target_ip, target_port, action_path, chat_id=None):
    """Generate HMAC-SHA256 signed URL for agent communication.

    payload = "{action_path}:{timestamp}"
    signature = hmac(chat_id_as_key, payload, sha256)
    Returns: https://{ip}:{port}{path}?t={timestamp}&sign={signature}
    """
    key = chat_id or CHAT_ID
    current_t = str(int(time.time()))
    payload = f"{action_path}:{current_t}"
    signature = hmac.new(
        key.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"https://{target_ip}:{target_port}{action_path}?t={current_t}&sign={signature}"


# ==========================================================
# Telegram Bot API Helpers
# ==========================================================


def tg_api_call(method, data):
    """Make a Telegram Bot API call using urllib with retry."""
    url = f"https://api.telegram.org/bot{TG_TOKEN}/{method}"
    debug_log(f"TG API -> {method} | chat_id={data.get('chat_id', 'N/A')}")
    payload = json.dumps(data).encode("utf-8")

    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                debug_log(f"TG API <- {method} OK")
                return result
        except Exception as e:
            debug_log(f"TG API <- {method} attempt {attempt+1}/3 FAILED: {type(e).__name__}: {e}")
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
            else:
                print(f"[TG API] {method} failed after 3 attempts: {e}")
    return None


def send_msg(chat_id, text):
    """Send a plain text message."""
    tg_api_call("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    })


def send_ui(chat_id, text, keyboard):
    """Send a message with inline keyboard.

    keyboard should be a list (Python object) for inline_keyboard.
    """
    tg_api_call("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": {"inline_keyboard": keyboard},
    })


def edit_msg(chat_id, message_id, text):
    """Edit a message's text."""
    tg_api_call("editMessageText", {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "Markdown",
    })


def edit_ui(chat_id, message_id, text, keyboard):
    """Edit a message with inline keyboard."""
    tg_api_call("editMessageText", {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": {"inline_keyboard": keyboard},
    })


def answer_callback_query(cb_id, text=None, show_alert=False):
    """Answer a callback query to clear the loading spinner."""
    data = {"callback_query_id": cb_id}
    if text:
        data["text"] = text
    if show_alert:
        data["show_alert"] = True
    tg_api_call("answerCallbackQuery", data)


def send_force_reply(chat_id, text):
    """Send a message with force_reply markup."""
    tg_api_call("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": {"force_reply": True},
    })


def edit_reply_markup(chat_id, message_id, keyboard):
    """Edit only the reply markup of a message."""
    tg_api_call("editMessageReplyMarkup", {
        "chat_id": chat_id,
        "message_id": message_id,
        "reply_markup": {"inline_keyboard": keyboard},
    })



# ==========================================================
# Agent Communication
# ==========================================================


def curl_agent_async(url):
    """Send non-blocking curl request to agent (self-signed TLS)."""
    try:
        subprocess.Popen(
            ["curl", "-k", "-s", "--connect-timeout", "5", "-m", "15", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def curl_agent_sync(url):
    """Send blocking curl request to agent, return response text."""
    debug_log(f"Agent curl -> {url}")
    try:
        result = subprocess.run(
            ["curl", "-k", "-s", "-v" if DEBUG else "-s", "--connect-timeout", "10", "-m", "30", url],
            capture_output=True, text=True, timeout=35
        )
        debug_log(f"Agent curl <- exit={result.returncode} stdout={result.stdout[:200]}")
        if DEBUG and result.stderr:
            debug_log(f"Agent curl stderr: {result.stderr[:500]}")
        if result.returncode != 0:
            debug_log(f"Agent curl FAILED: curl exit code {result.returncode}")
            return "FAILED"
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        debug_log(f"Agent curl TIMEOUT (>35s)")
        return "FAILED"
    except Exception as e:
        debug_log(f"Agent curl EXCEPTION: {type(e).__name__}: {e}")
        return "FAILED"


# ==========================================================
# Input Sanitization
# ==========================================================

RE_ALNUM = re.compile(r"[^a-zA-Z0-9]")
RE_NODE_NAME = re.compile(r"[^a-zA-Z0-9_.\-]")
RE_IP = re.compile(r"[^a-zA-Z0-9.:\[\]\-]")
RE_UNSAFE_CHARS = re.compile(r'["\'\`\$\|&;<>\n\r]')

PRIVATE_IP_PATTERNS = [
    re.compile(r"^127\."),
    re.compile(r"^10\."),
    re.compile(r"^192\.168\."),
    re.compile(r"^172\.(1[6-9]|2[0-9]|3[0-1])\."),
    re.compile(r"^169\.254\."),
    re.compile(r"^::1$"),
    re.compile(r"^localhost$", re.IGNORECASE),
    re.compile(r"^f[cd]", re.IGNORECASE),  # fc00::/7 (ULA)
]


def sanitize_node_name(s):
    if not s:
        return ""
    return RE_NODE_NAME.sub("", s)[:30]


def sanitize_alnum(s):
    if not s:
        return ""
    return RE_ALNUM.sub("", s)[:10]


def sanitize_ip(s):
    if not s:
        return ""
    return RE_IP.sub("", s)[:50]


def sanitize_port(s):
    if not s:
        return ""
    return re.sub(r"[^0-9]", "", s)[:5]


def sanitize_alias(s):
    if not s:
        return ""
    return RE_UNSAFE_CHARS.sub("", s)[:30]


def sanitize_chat_id(s):
    if not s:
        return ""
    return re.sub(r"[^0-9\-]", "", str(s))


def is_private_ip(ip):
    for pattern in PRIVATE_IP_PATTERNS:
        if pattern.search(ip):
            return True
    return False



# ==========================================================
# Command Handlers
# ==========================================================


def handle_svq(chat_id, text, cb_id=None, msg_id=None):
    """Handle deep-sea sonar data ingestion (svq|node|score|goog|nf|gpt)."""
    parts = text.split("|")
    if len(parts) < 3:
        if cb_id:
            answer_callback_query(cb_id, text="\u274c \u6570\u636e\u89e3\u6790\u5931\u8d25\uff0c\u5165\u5e93\u4e2d\u6b62\u3002", show_alert=True)
        return

    raw_node = parts[1] if len(parts) > 1 else ""
    raw_score = parts[2] if len(parts) > 2 else ""
    raw_goog = parts[3] if len(parts) > 3 else ""
    raw_nf = parts[4] if len(parts) > 4 else ""
    raw_gpt = parts[5] if len(parts) > 5 else ""

    node_id = sanitize_node_name(raw_node)
    score = re.sub(r"[^0-9]", "", raw_score)
    goog_st = RE_UNSAFE_CHARS.sub("", raw_goog)
    nf_st = RE_UNSAFE_CHARS.sub("", raw_nf)
    gpt_st = RE_UNSAFE_CHARS.sub("", raw_gpt)

    if node_id and score:
        db_exec(
            "INSERT INTO ip_trend_log (node_name, scam_score, goog_status, nf_status, gpt_status) "
            "VALUES (?, ?, ?, ?, ?);",
            (node_id, int(score), goog_st, nf_st, gpt_st)
        )
        if cb_id:
            answer_callback_query(cb_id, text="\u2705 \u62a5\u544a\u5df2\u6210\u529f\u5f55\u5165\u8d8b\u52bf\u5e93\uff01")
        if msg_id:
            keyboard = [
                [{"text": "\u2705 \u6b64\u62a5\u544a\u5df2\u5b58\u6863", "callback_data": "ignore"}],
                [{"text": "\u2699\ufe0f \u8c03\u51fa\u8be5\u8282\u70b9\u63a7\u5236\u53f0", "callback_data": f"manage:{node_id}"}],
            ]
            edit_reply_markup(chat_id, msg_id, keyboard)
    else:
        if cb_id:
            answer_callback_query(cb_id, text="\u274c \u6570\u636e\u89e3\u6790\u5931\u8d25\uff0c\u5165\u5e93\u4e2d\u6b62\u3002", show_alert=True)


def handle_register(chat_id, text):
    """Handle #REGISTER# messages from agents."""
    reg_line = ""
    for line in text.split("\n"):
        if "#REGISTER#" in line:
            reg_line = line.replace("`", "").strip()
            break
    if not reg_line:
        return

    parts = reg_line.split("|")
    field_count = len(parts)

    if field_count >= 7:
        _, raw_region, raw_node, raw_ip, raw_port, raw_alias, raw_ota = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], parts[6]
    elif field_count == 6:
        _, raw_region, raw_node, raw_ip, raw_port, raw_alias = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
        raw_ota = "false"
    elif field_count == 5:
        _, raw_region, raw_node, raw_ip, raw_port = parts[0], parts[1], parts[2], parts[3], parts[4]
        raw_alias = raw_node
        raw_ota = "false"
    else:
        _, raw_node, raw_ip, raw_port = parts[0], parts[1] if len(parts) > 1 else "", parts[2] if len(parts) > 2 else "", parts[3] if len(parts) > 3 else ""
        raw_region = "UNKNOWN"
        raw_alias = raw_node
        raw_ota = "false"

    s_chat_id = sanitize_chat_id(chat_id)
    agent_region = sanitize_alnum(raw_region)
    node_name = sanitize_node_name(raw_node)
    agent_ip = sanitize_ip(raw_ip)
    agent_port = sanitize_port(raw_port)
    node_alias = sanitize_alias(raw_alias) or node_name
    agent_ota = re.sub(r"[^a-z]", "", raw_ota.lower()) or "false"

    # SSRF protection
    if is_private_ip(agent_ip):
        send_msg(s_chat_id, "\u26d4 **\u5b89\u5168\u62e6\u622a**\uff1a\u7981\u6b62\u6ce8\u518c\u5185\u7f51\u6216\u56de\u73af IP\uff0c\u9632\u6b62 SSRF \u653b\u51fb\u6e17\u900f\u3002")
        return

    if not node_name or not agent_ip or not agent_port or not s_chat_id:
        send_msg(s_chat_id, "\u26d4 **\u5b89\u5168\u62e6\u622a**\uff1a\u68c0\u6d4b\u5230\u975e\u6cd5\u6ce8\u518c\u8f7d\u8377\uff0c\u8bf7\u6c42\u5df2\u62d2\u7edd\u3002")
        return

    db_exec(
        "INSERT INTO nodes (chat_id, node_name, agent_ip, agent_port, last_seen, region, node_alias, enable_ota) "
        "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?) "
        "ON CONFLICT(chat_id, node_name) DO UPDATE SET "
        "agent_ip=?, agent_port=?, last_seen=CURRENT_TIMESTAMP, region=?, node_alias=?, enable_ota=?;",
        (s_chat_id, node_name, agent_ip, agent_port, agent_region, node_alias, agent_ota,
         agent_ip, agent_port, agent_region, node_alias, agent_ota)
    )
    send_msg(s_chat_id, f"\u2705 **\u53f8\u4ee4\u90e8\u786e\u8ba4 (v{MASTER_VERSION})**\n\u8282\u70b9 `{node_alias}` \u6863\u6848\u5df2\u5f55\u5165\uff01")

    # Show region radar
    rows = db_exec(
        "SELECT region, COUNT(*) as cnt FROM nodes WHERE chat_id=? GROUP BY region;",
        (s_chat_id,)
    )
    if rows:
        btns = []
        for row in rows:
            region_name = row[0] or "UNKNOWN"
            node_count = row[1]
            flag = get_flag(region_name)
            btns.append([{"text": f"{flag} {region_name} ({node_count} \u53f0)", "callback_data": f"region:{region_name}"}])
        send_ui(s_chat_id, "\U0001f30d **\u5168\u89c6\u754c\u6218\u7565\u96f7\u8fbe**\n\u8bf7\u9009\u62e9\u8981\u68c0\u9605\u7684\u6218\u533a\uff1a", btns)




def handle_start_menu(chat_id, msg_id=None):
    """Handle /start and /menu commands - show main control panel."""
    s_chat_id = sanitize_chat_id(chat_id)

    # Check remote version
    remote_ver = ""
    try:
        req = urllib.request.Request(f"{REPO_RAW_URL}/version.txt")
        with urllib.request.urlopen(req, timeout=3) as resp:
            for line in resp.read().decode("utf-8").splitlines():
                if line.startswith("MASTER_VERSION="):
                    remote_ver = line.split("=", 1)[1].strip()
                    break
    except Exception:
        pass

    ver_info = f"\u5f53\u524d\u7248\u672c: `v{MASTER_VERSION}`"
    btn_master_ota = None

    if remote_ver:
        if remote_ver != MASTER_VERSION:
            ver_info = f"{ver_info}\n\u2728 **\u53d1\u73b0\u65b0\u7248\u672c**: `v{remote_ver}` (\u53ef\u6267\u884c\u4e2d\u67a2\u70ed\u91cd\u8f7d)"
            if IS_OFFICIAL_GATEWAY != "true" and ENABLE_MASTER_OTA == "true":
                btn_master_ota = [{"text": f"\U0001f199 \u5347\u7ea7\u63a7\u5236\u4e2d\u67a2\u81f3 v{remote_ver}", "callback_data": "master_ota_confirm"}]
        else:
            ver_info = f"\u5f53\u524d\u7248\u672c: `v{MASTER_VERSION}` (\u2705\u5df2\u662f\u6700\u65b0)"

    rows = db_exec("SELECT COUNT(*) FROM nodes WHERE chat_id=?;", (s_chat_id,))
    node_count = rows[0][0] if rows else 0

    btns = []
    if btn_master_ota:
        btns.append(btn_master_ota)

    if IS_OFFICIAL_GATEWAY != "true":
        btns.extend([
            [{"text": "\U0001f30d \u8fdb\u5165\u5168\u7403\u96f7\u8fbe (\u7ba1\u7406\u8282\u70b9)", "callback_data": "list_nodes"}],
            [{"text": "\U0001f680 \u5524\u9192\u5168\u5c40\u5de1\u903b", "callback_data": "all_run"},
             {"text": "\U0001f4ca \u83b7\u53d6\u5168\u5c40\u7b80\u62a5", "callback_data": "all_reports"}],
            [{"text": "\U0001f504 \u5168\u7f51\u8282\u70b9 OTA \u70ed\u91cd\u8f7d", "callback_data": "all_ota_confirm"}],
            [{"text": "\U0001f31f \u524d\u5f80 GitHub \u70b9\u4eae\u661f\u6807", "url": "https://github.com/XingLingQAQ/IP-Sentinel"}],
        ])
    else:
        btns.extend([
            [{"text": "\U0001f30d \u8fdb\u5165\u5168\u7403\u96f7\u8fbe (\u7ba1\u7406\u8282\u70b9)", "callback_data": "list_nodes"}],
            [{"text": "\U0001f680 \u5524\u9192\u5168\u5c40\u5de1\u903b", "callback_data": "all_run"},
             {"text": "\U0001f4ca \u83b7\u53d6\u5168\u5c40\u7b80\u62a5", "callback_data": "all_reports"}],
            [{"text": "\U0001f31f \u524d\u5f80 GitHub \u70b9\u4eae\u661f\u6807", "url": "https://github.com/XingLingQAQ/IP-Sentinel"}],
        ])

    text_msg = (
        f"\U0001f6e1\ufe0f **IP-Sentinel \u63a7\u5236\u4e2d\u67a2**\n{ver_info}\n\n"
        f"\U0001f4ca \u8282\u70b9\u72b6\u6001: \u5171\u6709 `{node_count}` \u53f0\u8282\u70b9\u5728\u7ebf\n"
        f"\u6b22\u8fce\u56de\u6765\uff0c\u7ba1\u7406\u8005\u3002\u8bf7\u4e0b\u8fbe\u7cfb\u7edf\u6307\u4ee4\uff1a"
    )

    if msg_id:
        edit_ui(s_chat_id, msg_id, text_msg, btns)
    else:
        send_ui(s_chat_id, text_msg, btns)


def handle_list_nodes(chat_id, msg_id=None):
    """Handle list_nodes callback - show regions grouped."""
    s_chat_id = sanitize_chat_id(chat_id)
    rows = db_exec(
        "SELECT region, COUNT(*) as cnt FROM nodes WHERE chat_id=? GROUP BY region;",
        (s_chat_id,)
    )
    if not rows:
        send_msg(s_chat_id, "\u26a0\ufe0f \u60a8\u540d\u4e0b\u6682\u65e0\u5728\u7ebf\u8282\u70b9\uff0c\u8bf7\u5148\u5728\u8fb9\u7f18\u673a\u6267\u884c\u90e8\u7f72\u3002")
        return

    btns = []
    for row in rows:
        region_name = row[0] or "UNKNOWN"
        node_count = row[1]
        flag = get_flag(region_name)
        btns.append([{"text": f"{flag} {region_name} ({node_count} \u53f0)", "callback_data": f"region:{region_name}"}])
    btns.append([{"text": "\U0001f3e0 \u56de\u5230\u53f8\u4ee4\u90e8", "callback_data": "/start"}])

    text_msg = "\U0001f30d **\u5168\u89c6\u754c\u6218\u7565\u96f7\u8fbe**\n\u5df2\u4e3a\u60a8\u805a\u5408\u5f53\u524d\u8230\u961f\u7684\u90e8\u7f72\u5927\u533a\uff0c\u8bf7\u9009\u62e9\u8981\u68c0\u9605\u7684\u6218\u533a\uff1a"
    if msg_id:
        edit_ui(s_chat_id, msg_id, text_msg, btns)
    else:
        send_ui(s_chat_id, text_msg, btns)


def handle_region(chat_id, region_code, msg_id=None):
    """Handle region:XX callback - list nodes in region."""
    s_chat_id = sanitize_chat_id(chat_id)
    target_region = sanitize_alnum(region_code)

    rows = db_exec(
        "SELECT node_name, IFNULL(node_alias, node_name) FROM nodes WHERE chat_id=? AND region=?;",
        (s_chat_id, target_region)
    )
    if not rows:
        send_msg(s_chat_id, "\u26a0\ufe0f \u8be5\u6218\u533a\u4e0b\u6682\u65e0\u53ef\u7528\u8282\u70b9\u3002")
        return

    btns = []
    row_buf = []
    for row in rows:
        n_name = row[0]
        n_alias = row[1]
        if not n_name:
            continue
        row_buf.append({"text": f"\U0001f5a5\ufe0f {n_alias}", "callback_data": f"manage:{n_name}"})
        if len(row_buf) == 2:
            btns.append(row_buf)
            row_buf = []
    if row_buf:
        btns.append(row_buf)

    btns.append([
        {"text": "\u2b05\ufe0f \u8fd4\u56de\u6218\u533a\u5730\u56fe", "callback_data": "list_nodes"},
        {"text": "\U0001f3e0 \u56de\u5230\u53f8\u4ee4\u90e8", "callback_data": "/start"},
    ])

    text_msg = f"\U0001f4cd **[{target_region}] \u6218\u533a\u54e8\u5175\u77e9\u9635**\n\u8bf7\u9501\u5b9a\u8981\u6267\u884c\u6218\u672f\u52a8\u4f5c\u7684\u5177\u4f53\u76ee\u6807\uff1a"
    if msg_id:
        edit_ui(s_chat_id, msg_id, text_msg, btns)
    else:
        send_ui(s_chat_id, text_msg, btns)




def _build_manage_panel(s_chat_id, target_node):
    """Build the manage panel keyboard and text for a node."""
    rows = db_exec(
        "SELECT enable_google, enable_trust, enable_ota, agent_ip, IFNULL(last_seen, '\u672a\u77e5') "
        "FROM nodes WHERE chat_id=? AND node_name=? LIMIT 1;",
        (s_chat_id, target_node)
    )
    if not rows:
        return None, None

    row = rows[0]
    st_google = row[0]
    st_trust = row[1]
    st_ota = row[2]
    a_ip = row[3]
    last_seen = row[4]

    target_alias_rows = db_exec(
        "SELECT IFNULL(node_alias, node_name) FROM nodes WHERE chat_id=? AND node_name=? LIMIT 1;",
        (s_chat_id, target_node)
    )
    target_alias = target_alias_rows[0][0] if target_alias_rows else target_node

    # Toggle button states
    if st_google == "true":
        btn_g_text = "\U0001f7e2 Google\u5de1\u903b: \u5df2\u5f00"
        act_g = "false"
    else:
        btn_g_text = "\U0001f534 Google\u5de1\u903b: \u5df2\u505c"
        act_g = "true"

    if st_trust == "true":
        btn_t_text = "\U0001f7e2 \u4fe1\u7528\u51c0\u5316: \u5df2\u5f00"
        act_t = "false"
    else:
        btn_t_text = "\U0001f534 \u4fe1\u7528\u51c0\u5316: \u5df2\u505c"
        act_t = "true"

    btn_action = [
        [{"text": "\U0001f4cd \u89e6\u53d1 Google \u7ea0\u504f", "callback_data": f"google:{target_node}"},
         {"text": "\U0001f6e1\ufe0f \u89e6\u53d1\u4fe1\u7528\u51c0\u5316", "callback_data": f"trust:{target_node}"}],
        [{"text": "\U0001f50d \u6295\u653e\u6df1\u6d77\u58f0\u7eb3 (\u67e5IP\u8d28\u91cf)", "callback_data": f"quality:{target_node}"},
         {"text": "\U0001f4c8 \u67e5\u770b IP \u6c61\u67d3\u8d8b\u52bf\u56fe", "callback_data": f"trend:{target_node}"}],
        [{"text": "\U0001f4dc \u63d0\u53d6\u7ec8\u7aef\u5b9e\u65f6\u65e5\u5fd7", "callback_data": f"log:{target_node}"},
         {"text": "\U0001f4ca \u751f\u6210\u5355\u673a\u6218\u62a5", "callback_data": f"report:{target_node}"}],
    ]
    btn_toggle = [
        {"text": btn_g_text, "callback_data": f"toggle:google:{target_node}:{act_g}"},
        {"text": btn_t_text, "callback_data": f"toggle:trust:{target_node}:{act_t}"},
    ]

    btn_config_row = [{"text": "\u270f\ufe0f \u66f4\u6539\u7ec8\u7aef\u5c55\u793a\u4ee3\u53f7", "callback_data": f"rename:{target_node}"}]
    if IS_OFFICIAL_GATEWAY != "true" and st_ota == "true":
        btn_config_row.append({"text": "\U0001f199 OTA \u9759\u9ed8\u5347\u7ea7", "callback_data": f"ota_confirm:{target_node}"})

    btn_danger = [
        {"text": "\U0001f5d1\ufe0f \u4ece\u4e2d\u67a2\u9500\u6bc1\u8be5\u6863\u6848", "callback_data": f"del:{target_node}"},
        {"text": "\u2b05\ufe0f \u8fd4\u56de\u6218\u533a\u5217\u8868", "callback_data": "list_nodes"},
    ]

    btns = btn_action + [btn_toggle, btn_config_row, btn_danger]
    text_msg = (
        f"\u2699\ufe0f **\u76ee\u6807\u9501\u5b9a**: `{target_alias}`\n"
        f"(\u5e95\u5c42\u6807\u8bc6: `{target_node}`)\n"
        f"\U0001f310 IP \u5750\u6807: `{a_ip}`\n"
        f"\U0001f552 \u6700\u540e\u901a\u8baf: `{last_seen}`\n\n"
        f"\u8bf7\u4e0b\u8fbe\u7cbe\u786e\u63a7\u5236\u6307\u4ee4\uff1a"
    )
    return text_msg, btns


def handle_manage(chat_id, node_name, msg_id=None):
    """Handle manage:NODE callback - show node control panel."""
    s_chat_id = sanitize_chat_id(chat_id)
    target_node = sanitize_node_name(node_name)

    text_msg, btns = _build_manage_panel(s_chat_id, target_node)
    if text_msg is None:
        send_msg(s_chat_id, "\u274c \u6570\u636e\u5e93\u4e2d\u672a\u627e\u5230\u8be5\u8282\u70b9\u7684\u901a\u8baf\u5730\u5740\u3002")
        return

    if msg_id:
        edit_ui(s_chat_id, msg_id, text_msg, btns)
    else:
        send_ui(s_chat_id, text_msg, btns)




def handle_action(chat_id, action_type, target_node, msg_id=None):
    """Handle google:NODE, trust:NODE, run:NODE, report:NODE, log:NODE, quality:NODE callbacks."""
    s_chat_id = sanitize_chat_id(chat_id)
    target_node = sanitize_node_name(target_node)

    rows = db_exec(
        "SELECT agent_ip, agent_port FROM nodes WHERE chat_id=? AND node_name=? LIMIT 1;",
        (s_chat_id, target_node)
    )
    if not rows:
        send_msg(s_chat_id, "\u274c \u6570\u636e\u5e93\u4e2d\u672a\u627e\u5230\u8be5\u8282\u70b9\u7684\u901a\u8baf\u5730\u5740\u3002")
        return

    agent_ip = rows[0][0]
    agent_port = rows[0][1]

    if not agent_ip or not agent_port:
        send_msg(s_chat_id, "\u274c \u6570\u636e\u5e93\u4e2d\u672a\u627e\u5230\u8be5\u8282\u70b9\u7684\u901a\u8baf\u5730\u5740\u3002")
        return

    # Show progress with back button in case agent is slow
    progress_msg = f"\u23f3 \u6b63\u5728\u5411 `{target_node}` ({agent_ip}) \u4e0b\u53d1 [{action_type}] \u6307\u4ee4\uff0c\u8bf7\u7a0d\u5019..."
    progress_btn = [[{"text": "\U0001f3e0 \u4e3b\u83dc\u5355", "callback_data": "/start"}]]
    if msg_id:
        edit_ui(s_chat_id, msg_id, progress_msg, progress_btn)
    else:
        send_ui(s_chat_id, progress_msg, progress_btn)

    target_url = generate_signed_url(agent_ip, agent_port, f"/trigger_{action_type}", s_chat_id)
    response = curl_agent_sync(target_url)

    if response == "FAILED":
        text_res = "\u274c \u6307\u4ee4\u4e0b\u53d1\u8d85\u65f6\u6216\u5931\u8d25\uff01\u4e3a\u4fdd\u62a4\u94fe\u8def\u5b89\u5168\uff0c\u5df2\u7ec8\u6b62\u901a\u4fe1 (\u4e25\u7981\u964d\u7ea7\u4e3a HTTP)\u3002"
    elif "403" in response:
        text_res = "\u26a0\ufe0f **\u62d2\u7edd\u6267\u884c**\uff1a\u8be5\u8282\u70b9\u672a\u5728\u672c\u5730\u5f00\u542f\u6b64\u6a21\u5757\uff0c\u8bf7\u68c0\u67e5\u5b89\u88c5\u65f6\u7684\u914d\u7f6e\uff01"
    else:
        if action_type in ("google", "run"):
            text_res = f"\u2705 \u8282\u70b9 `{target_node}` \u56de\u5e94: \U0001f4cd Google \u7ea0\u504f\u7a0b\u5e8f\u542f\u52a8\u3002"
        elif action_type == "trust":
            text_res = f"\u2705 \u8282\u70b9 `{target_node}` \u56de\u5e94: \U0001f6e1\ufe0f IP \u4fe1\u7528\u51c0\u5316\u7a0b\u5e8f\u542f\u52a8\u3002"
        elif action_type == "quality":
            text_res = f"\u2705 \u8282\u70b9 `{target_node}` \u56de\u5e94: \U0001f50d \u6df1\u6d77\u58f0\u7eb3\u5df2\u6295\u653e\uff01\u8bf7\u7b49\u5f85\u5f02\u6b65\u6218\u62a5\u56de\u4f20\u3002"
        elif action_type == "log":
            text_res = f"\u2705 \u8282\u70b9 `{target_node}` \u6b63\u5728\u6293\u53d6\u65e5\u5fd7..."
        else:
            text_res = f"\u2705 \u8282\u70b9 `{target_node}` \u63a5\u6536\u6307\u4ee4: {action_type}"

    # Append a "back to node panel" button so user can navigate after action
    back_btn = [[{"text": "\u2b05\ufe0f \u8fd4\u56de\u8282\u70b9\u9762\u677f", "callback_data": f"manage:{target_node}"},
                 {"text": "\U0001f3e0 \u4e3b\u83dc\u5355", "callback_data": "/start"}]]
    if msg_id:
        edit_ui(s_chat_id, msg_id, text_res, back_btn)
    else:
        send_ui(s_chat_id, text_res, back_btn)


def handle_toggle(chat_id, mod_name, target_node, target_state, msg_id=None):
    """Handle toggle:MOD:NODE:STATE callback."""
    s_chat_id = sanitize_chat_id(chat_id)
    target_node = sanitize_node_name(target_node)

    rows = db_exec(
        "SELECT agent_ip, agent_port FROM nodes WHERE chat_id=? AND node_name=? LIMIT 1;",
        (s_chat_id, target_node)
    )
    if not rows:
        send_msg(s_chat_id, "\u274c \u6570\u636e\u5e93\u4e2d\u672a\u627e\u5230\u8be5\u8282\u70b9\u7684\u901a\u8baf\u5730\u5740\u3002")
        return

    agent_ip = rows[0][0]
    agent_port = rows[0][1]

    if not agent_ip or not agent_port:
        return

    target_url = generate_signed_url(agent_ip, agent_port, "/trigger_toggle", s_chat_id)
    target_url += f"&mod={mod_name}&state={target_state}"

    response = curl_agent_sync(target_url)

    if "Action Accepted" in response:
        # Update DB
        if mod_name in ("google", "trust", "ota"):
            db_exec(
                f"UPDATE nodes SET enable_{mod_name}=? WHERE chat_id=? AND node_name=?;",
                (target_state, s_chat_id, target_node)
            )

        # Rebuild manage panel with success message
        text_msg, btns = _build_manage_panel(s_chat_id, target_node)
        if text_msg:
            text_msg += f"\n\n\u2705 **\u6267\u884c\u6210\u529f**: \u6a21\u5757 [{mod_name}] \u72b6\u6001\u5df2\u5207\u6362\u4e3a {target_state}\uff01"
            if msg_id:
                edit_ui(s_chat_id, msg_id, text_msg, btns)
            else:
                send_ui(s_chat_id, text_msg, btns)
    else:
        send_msg(s_chat_id, "\u274c \u6307\u4ee4\u4e0b\u53d1\u5931\u8d25\uff0c\u5b89\u5168\u7b56\u7565\u7981\u6b62\u964d\u7ea7\u91cd\u8bd5\u3002")




def handle_rename_prompt(chat_id, target_node):
    """Handle rename:NODE callback - send force_reply message."""
    s_chat_id = sanitize_chat_id(chat_id)
    target_node = sanitize_node_name(target_node)
    send_force_reply(
        s_chat_id,
        f"\u270f\ufe0f \u8bf7\u56de\u590d\u672c\u6d88\u606f\u4ee5\u91cd\u547d\u540d\u8282\u70b9:\n`{target_node}`\n(\u4ec5\u9650\u4e2d\u82f1\u6587\u3001\u6570\u5b57\uff0c\u6700\u957f20\u5b57\u7b26)"
    )


def handle_do_rename(chat_id, target_node, new_alias):
    """Handle do_rename:NODE:ALIAS - send rename to agent."""
    s_chat_id = sanitize_chat_id(chat_id)
    target_node = sanitize_node_name(target_node)
    new_alias = sanitize_alias(new_alias)

    rows = db_exec(
        "SELECT agent_ip, agent_port FROM nodes WHERE chat_id=? AND node_name=? LIMIT 1;",
        (s_chat_id, target_node)
    )
    if not rows:
        send_msg(s_chat_id, "\u274c \u6570\u636e\u5e93\u4e2d\u672a\u627e\u5230\u8be5\u8282\u70b9\u7684\u901a\u8baf\u5730\u5740\u3002")
        return

    agent_ip = rows[0][0]
    agent_port = rows[0][1]

    if not agent_ip or not agent_port:
        send_msg(s_chat_id, "\u274c \u6570\u636e\u5e93\u4e2d\u672a\u627e\u5230\u8be5\u8282\u70b9\u7684\u901a\u8baf\u5730\u5740\u3002")
        return

    send_msg(s_chat_id, f"\u23f3 \u6b63\u5728\u5411 `{target_node}` \u4e0b\u53d1\u91cd\u547d\u540d\u6307\u4ee4\uff0c\u6b63\u5728\u5efa\u7acb\u52a0\u5bc6\u96a7\u9053...")

    target_url = generate_signed_url(agent_ip, agent_port, "/trigger_rename", s_chat_id)
    # Base64 encode the alias with URL-safe encoding
    alias_b64 = b64encode(new_alias.encode()).decode().rstrip("=").replace("+", "-").replace("/", "_")
    target_url += f"&b64={alias_b64}"

    response = curl_agent_sync(target_url)

    if response == "FAILED":
        send_msg(s_chat_id, "\u274c \u6307\u4ee4\u4e0b\u53d1\u8d85\u65f6\uff01\u4e3a\u9632\u8303\u52ab\u6301\u98ce\u9669\uff0c\u5df2\u7ec8\u6b62\u8bf7\u6c42\u3002")
    elif "Action Accepted" in response:
        db_exec(
            "UPDATE nodes SET node_alias=? WHERE chat_id=? AND node_name=?;",
            (new_alias, s_chat_id, target_node)
        )
        send_msg(s_chat_id, f"\u2705 \u901a\u8baf\u6210\u529f\uff01\u8282\u70b9\u522b\u540d\u5df2\u4e0b\u53d1: `{new_alias}`\n*(\u53f8\u4ee4\u90e8\u6863\u6848\u5df2\u81ea\u52a8\u5237\u65b0\uff0c\u96f7\u8fbe\u9762\u677f\u5df2\u540c\u6b65)*")
    else:
        send_msg(s_chat_id, f"\u26a0\ufe0f \u8282\u70b9\u62d2\u7edd\u4e86\u8bf7\u6c42\uff0c\u8bf7\u786e\u4fdd Agent \u5df2\u66f4\u65b0\u81f3 v3.5.2\n(\u56de\u4f20\u4fe1\u606f: `{response}`)")


def handle_delete(chat_id, target_node, msg_id=None):
    """Handle del:NODE callback - delete node from DB."""
    s_chat_id = sanitize_chat_id(chat_id)
    target_node = sanitize_node_name(target_node)

    # Verify ownership
    rows = db_exec(
        "SELECT 1 FROM nodes WHERE chat_id=? AND node_name=? LIMIT 1;",
        (s_chat_id, target_node)
    )
    if not rows:
        send_msg(s_chat_id, "\u26d4 **\u5b89\u5168\u62e6\u622a**\uff1a\u9500\u6bc1\u5931\u8d25\u3002\u76ee\u6807\u8282\u70b9\u4e0d\u5b58\u5728\u6216\u60a8\u65e0\u6743\u8d8a\u6743\u64cd\u4f5c\uff01")
        return

    db_exec("DELETE FROM nodes WHERE chat_id=? AND node_name=?;", (s_chat_id, target_node))
    db_exec("DELETE FROM ip_trend_log WHERE node_name=?;", (target_node,))
    send_msg(s_chat_id, f"\U0001f5d1\ufe0f \u8282\u70b9 `{target_node}` \u7684\u6863\u6848\u53ca\u5386\u53f2\u6c61\u67d3\u8d8b\u52bf\u5df2\u4ece\u53f8\u4ee4\u90e8\u5f7b\u5e95\u9500\u6bc1\uff01")

    # Refresh region radar
    rows = db_exec(
        "SELECT region, COUNT(*) as cnt FROM nodes WHERE chat_id=? GROUP BY region;",
        (s_chat_id,)
    )
    if not rows:
        send_msg(s_chat_id, "\u26a0\ufe0f \u5f53\u524d\u53f8\u4ee4\u90e8\u5df2\u65e0\u4efb\u4f55\u8282\u70b9\u6302\u8f7d\u3002")
    else:
        btns = []
        for row in rows:
            region_name = row[0] or "UNKNOWN"
            node_count = row[1]
            flag = get_flag(region_name)
            btns.append([{"text": f"{flag} {region_name} ({node_count} \u53f0)", "callback_data": f"region:{region_name}"}])
        send_ui(s_chat_id, "\U0001f30d \u5237\u65b0\u540e\u7684\u5168\u89c6\u754c\u96f7\u8fbe\uff1a", btns)




def handle_trend(chat_id, target_node, msg_id=None):
    """Handle trend:NODE and /trend NODE - show IP trend history."""
    s_chat_id = sanitize_chat_id(chat_id)
    target_node = sanitize_node_name(target_node)

    rows = db_exec(
        "SELECT datetime(check_time, 'localtime'), scam_score, goog_status, nf_status, gpt_status "
        "FROM ip_trend_log WHERE node_name=? ORDER BY check_time DESC LIMIT 15;",
        (target_node,)
    )

    if not rows:
        text_res = f"\u26a0\ufe0f \u8282\u70b9 `{target_node}` \u6682\u65e0\u5386\u53f2\u4f53\u68c0\u6863\u6848\u3002\u8bf7\u5148\u6267\u884c [\U0001f50d \u6295\u653e\u6df1\u6d77\u58f0\u7eb3] \u8fdb\u884c\u63a2\u6d4b\u3002"
        btns = [[{"text": "\u2699\ufe0f \u8c03\u51fa\u8be5\u8282\u70b9\u63a7\u5236\u53f0", "callback_data": f"manage:{target_node}"}]]
        if msg_id:
            edit_ui(s_chat_id, msg_id, text_res, btns)
        else:
            send_ui(s_chat_id, text_res, btns)
        return

    # Get alias
    alias_rows = db_exec(
        "SELECT IFNULL(node_alias, node_name) FROM nodes WHERE chat_id=? AND node_name=? LIMIT 1;",
        (s_chat_id, target_node)
    )
    target_alias = alias_rows[0][0] if alias_rows else target_node

    text_res = f"\U0001f4c8 *[{target_alias}] \u5386\u53f2\u6001\u52bf\u611f\u77e5 (\u8fd115\u6b21)*\n\n"
    text_res += "\u65f6\u95f4(\u672c\u5730)  | \u98ce\u9669 | \u8c37\u6b4c | NF | GPT\n"
    text_res += "-----------------------------------------\n"

    for row in rows:
        c_time = row[0] or ""
        score = row[1] if row[1] is not None else 0
        goog = row[2] or "\u672a\u77e5"
        nf = row[3] or "\u672a\u77e5"
        gpt = row[4] or "\u672a\u77e5"

        short_time = c_time[5:16] if len(c_time) >= 16 else c_time

        if int(score) <= 20:
            score_emj = "\U0001f7e2"
        elif int(score) <= 60:
            score_emj = "\U0001f7e1"
        else:
            score_emj = "\U0001f534"

        text_res += f"`{short_time}` | {score_emj}`{score}` | `{goog}` | `{nf}` | `{gpt}`\n"

    text_res += "\n_\U0001f4a1 \u63d0\u793a\uff1a\U0001f534\u98ce\u9669\u5206 >60 \u6781\u6613\u89e6\u53d1\u7f51\u9875\u9a8c\u8bc1\u7801\u62e6\u622a\uff1b\u8c37\u6b4c\u663e\u793a CN \u5373\u4e3a\u9ad8\u5371\u9001\u4e2d\u3002_"

    btns = [[{"text": "\u2699\ufe0f \u8c03\u51fa\u8be5\u8282\u70b9\u63a7\u5236\u53f0", "callback_data": f"manage:{target_node}"}]]
    if msg_id:
        edit_ui(s_chat_id, msg_id, text_res, btns)
    else:
        send_ui(s_chat_id, text_res, btns)


def handle_quality_cmd(chat_id, text):
    """Handle /quality NODE text command."""
    s_chat_id = sanitize_chat_id(chat_id)
    parts = text.split()
    if len(parts) < 2:
        send_msg(s_chat_id, "\u26a0\ufe0f \u8bf7\u6307\u5b9a\u76ee\u6807\u8282\u70b9\u3002\u4f8b\u5982: `/quality HK-1`\n\u6216\u901a\u8fc7\u96f7\u8fbe\u9762\u677f\u8fdb\u884c\u9009\u62e9\u64cd\u4f5c\u3002")
        return

    target_node = sanitize_node_name(parts[1])
    rows = db_exec(
        "SELECT agent_ip, agent_port FROM nodes WHERE chat_id=? AND node_name=? LIMIT 1;",
        (s_chat_id, target_node)
    )
    if not rows:
        send_msg(s_chat_id, "\u274c \u6570\u636e\u5e93\u4e2d\u672a\u627e\u5230\u8be5\u8282\u70b9\u7684\u901a\u8baf\u5730\u5740\u3002")
        return

    agent_ip = rows[0][0]
    agent_port = rows[0][1]

    if not agent_ip or not agent_port:
        send_msg(s_chat_id, "\u274c \u6570\u636e\u5e93\u4e2d\u672a\u627e\u5230\u8be5\u8282\u70b9\u7684\u901a\u8baf\u5730\u5740\u3002")
        return

    send_msg(s_chat_id, f"\u23f3 \u6b63\u5728\u5411 `{target_node}` ({agent_ip}) \u4e0b\u53d1 [quality] \u6307\u4ee4\uff0c\u8bf7\u7a0d\u5019...")
    target_url = generate_signed_url(agent_ip, agent_port, "/trigger_quality", s_chat_id)
    response = curl_agent_sync(target_url)

    if response == "FAILED":
        send_msg(s_chat_id, "\u274c \u6307\u4ee4\u4e0b\u53d1\u8d85\u65f6\u6216\u5931\u8d25\uff01\u8bf7\u68c0\u67e5\u8282\u70b9\u516c\u7f51 IP \u6216\u9632\u706b\u5899\u7aef\u53e3\u662f\u5426\u653e\u884c\u3002")
    elif "403" in response:
        send_msg(s_chat_id, "\u26a0\ufe0f **\u62d2\u7edd\u6267\u884c**\uff1a\u8be5\u8282\u70b9\u672a\u5728\u672c\u5730\u5f00\u542f\u6b64\u6a21\u5757\uff0c\u8bf7\u68c0\u67e5\u5b89\u88c5\u65f6\u7684\u914d\u7f6e\uff01")
    else:
        send_msg(s_chat_id, f"\u2705 \u8282\u70b9 `{target_node}` \u56de\u5e94: \U0001f50d \u6df1\u6d77\u58f0\u7eb3\u5df2\u6295\u653e\uff01\u8bf7\u7b49\u5f85\u5f02\u6b65\u6218\u62a5\u56de\u4f20\u3002")


def handle_trend_cmd(chat_id, text):
    """Handle /trend NODE text command."""
    s_chat_id = sanitize_chat_id(chat_id)
    parts = text.split()
    if len(parts) < 2:
        send_msg(s_chat_id, "\u26a0\ufe0f \u8bf7\u6307\u5b9a\u76ee\u6807\u8282\u70b9\u3002\u4f8b\u5982: `/trend HK-1`\n\u6216\u901a\u8fc7\u96f7\u8fbe\u9762\u677f\u8fdb\u884c\u9009\u62e9\u64cd\u4f5c\u3002")
        return
    target_node = sanitize_node_name(parts[1])
    handle_trend(s_chat_id, target_node)




def handle_all_run(chat_id):
    """Handle all_run callback - send /trigger_run to all nodes."""
    s_chat_id = sanitize_chat_id(chat_id)
    rows = db_exec(
        "SELECT node_name, agent_ip, agent_port FROM nodes WHERE chat_id=?;",
        (s_chat_id,)
    )
    if not rows:
        send_msg(s_chat_id, "\u26a0\ufe0f \u60a8\u540d\u4e0b\u6682\u65e0\u5728\u7ebf\u8282\u70b9\u3002")
        return

    send_msg(s_chat_id, "\U0001f4e2 **\u53f8\u4ee4\u90e8\u6307\u4ee4\u4e0b\u8fbe\uff1a\u6b63\u5728\u5524\u9192\u6240\u6709\u54e8\u5175\u6267\u884c\u7cfb\u7edf\u7ef4\u62a4...**")
    for row in rows:
        n_name, a_ip, a_port = row[0], row[1], row[2]
        target_url = generate_signed_url(a_ip, a_port, "/trigger_run", s_chat_id)
        curl_agent_async(target_url)
        time.sleep(0.2)


def handle_all_reports(chat_id):
    """Handle all_reports callback - send /trigger_report to all nodes."""
    s_chat_id = sanitize_chat_id(chat_id)
    rows = db_exec(
        "SELECT node_name, agent_ip, agent_port FROM nodes WHERE chat_id=?;",
        (s_chat_id,)
    )
    if not rows:
        send_msg(s_chat_id, "\u26a0\ufe0f \u60a8\u540d\u4e0b\u6682\u65e0\u5728\u7ebf\u8282\u70b9\u3002")
        return

    send_msg(s_chat_id, "\U0001f4e2 **\u53f8\u4ee4\u90e8\u6307\u4ee4\u4e0b\u8fbe\uff1a\u6b63\u5728\u53ec\u5524\u6240\u6709\u54e8\u5175\u56de\u4f20\u7b80\u62a5...**\n*(\u4e3a\u9632\u6b62\u89e6\u53d1 TG \u5b98\u65b9\u9650\u6d41\uff0c\u7b80\u62a5\u5c06\u6392\u961f\u4f9d\u6b21\u9001\u8fbe\uff0c\u8bf7\u8010\u5fc3\u7b49\u5f85)*")
    for row in rows:
        n_name, a_ip, a_port = row[0], row[1], row[2]
        target_url = generate_signed_url(a_ip, a_port, "/trigger_report", s_chat_id)
        curl_agent_async(target_url)
        time.sleep(2)


def handle_all_ota_confirm(chat_id, msg_id=None):
    """Handle all_ota_confirm callback - show warning."""
    s_chat_id = sanitize_chat_id(chat_id)
    btns = [
        [{"text": "\U0001f6a8 \u6211\u5df2\u4e86\u89e3\u98ce\u9669\uff0c\u4e0b\u53d1\u6838\u6309\u94ae\u6307\u4ee4\uff01", "callback_data": "all_ota_execute"}],
        [{"text": "\u53d6\u6d88\u64cd\u4f5c", "callback_data": "/start"}],
    ]
    warning_msg = (
        "\u2622\ufe0f **\u3010\u6700\u9ad8\u6307\u4ee4\uff1a\u5168\u8230\u961f OTA \u5347\u7ea7\u3011**\n\n"
        "\u6b64\u64cd\u4f5c\u5c06\u5411\u60a8\u540d\u4e0b**\u6240\u6709\u5f00\u542f OTA \u6743\u9650\u7684\u8282\u70b9**\u4e0b\u53d1\u91cd\u7ec4\u6307\u4ee4\uff0c"
        "\u5f3a\u5236\u4ece\u4e91\u7aef\u62c9\u53d6\u6700\u65b0\u4ee3\u7801\u5e76\u8fdb\u884c\u70ed\u91cd\u8f7d\u3002\n\n"
        "\u26a0\ufe0f **\u6838\u6309\u94ae\u98ce\u9669\u63d0\u793a**\uff1a\n"
        "1. \u5347\u7ea7\u8fc7\u7a0b\u4e2d\u5b88\u62a4\u8fdb\u7a0b\u4f1a\u77ed\u6682\u91cd\u542f\uff0c\u8282\u70b9\u53ef\u80fd\u51fa\u73b0\u4e34\u65f6\u79bb\u7ebf\u3002\n"
        "2. \u82e5\u9047 GitHub \u6e90\u5c4f\u853d\u6216\u7f51\u7edc\u6781\u5ea6\u6076\u52a3\uff0c\u5c11\u6570\u8282\u70b9\u53ef\u80fd\u9700\u8981\u624b\u52a8\u5e72\u9884\u3002\n\n"
        "**\u662f\u5426\u786e\u5b9a\u6302\u8f7d\u5e76\u6267\u884c OTA \u6307\u4ee4\uff1f**"
    )
    send_ui(s_chat_id, warning_msg, btns)


def handle_all_ota_execute(chat_id):
    """Handle all_ota_execute callback - send OTA to all enabled nodes."""
    s_chat_id = sanitize_chat_id(chat_id)
    rows = db_exec(
        "SELECT node_name, agent_ip, agent_port FROM nodes WHERE chat_id=? AND enable_ota='true';",
        (s_chat_id,)
    )
    if not rows:
        send_msg(s_chat_id, "\u26a0\ufe0f \u60a8\u540d\u4e0b\u6682\u65e0\u5f00\u542f OTA \u6743\u9650\u7684\u5728\u7ebf\u8282\u70b9\u3002")
        return

    send_msg(s_chat_id, "\U0001f4e2 **\u53f8\u4ee4\u90e8\u6307\u4ee4\u4e0b\u8fbe\uff1a\u6b63\u5728\u5524\u9192\u5168\u8230\u961f\u6267\u884c OTA \u5347\u7ea7...**\n*(\u8282\u70b9\u5347\u7ea7\u6210\u529f\u540e\u4f1a\u4e3b\u52a8\u53d1\u56de\u65b0\u7684\u5165\u5e93\u786e\u8ba4\uff0c\u8bf7\u6ce8\u610f\u67e5\u6536)*")
    for row in rows:
        n_name, a_ip, a_port = row[0], row[1], row[2]
        target_url = generate_signed_url(a_ip, a_port, "/trigger_ota", s_chat_id)
        curl_agent_async(target_url)
        time.sleep(0.3)




def handle_ota_confirm(chat_id, target_node, msg_id=None):
    """Handle ota_confirm:NODE - show confirmation."""
    s_chat_id = sanitize_chat_id(chat_id)
    target_node = sanitize_node_name(target_node)
    btns = [
        [{"text": "\U0001f6a8 \u786e\u8ba4\u6267\u884c\u8fdc\u7a0b\u5347\u7ea7", "callback_data": f"ota_execute:{target_node}"}],
        [{"text": "\u53d6\u6d88", "callback_data": f"manage:{target_node}"}],
    ]
    text_msg = (
        f"\u2622\ufe0f **\u64cd\u4f5c\u786e\u8ba4**\uff1a\u5373\u5c06\u5411 `{target_node}` \u4e0b\u53d1 OTA \u70ed\u66f4\u65b0\u6307\u4ee4\u3002\n"
        f"\u8282\u70b9\u66f4\u65b0\u5b8c\u6210\u540e\u4f1a\u81ea\u52a8\u53d1\u9001\u5305\u542b\u65b0\u7248\u672c\u53f7\u7684\u6ce8\u518c\u56de\u6267\uff0c\u786e\u5b9a\u6267\u884c\uff1f"
    )
    send_ui(s_chat_id, text_msg, btns)


def handle_ota_execute(chat_id, target_node, msg_id=None):
    """Handle ota_execute:NODE - send OTA to single node."""
    s_chat_id = sanitize_chat_id(chat_id)
    target_node = sanitize_node_name(target_node)

    rows = db_exec(
        "SELECT agent_ip, agent_port FROM nodes WHERE chat_id=? AND node_name=? LIMIT 1;",
        (s_chat_id, target_node)
    )
    if not rows:
        send_msg(s_chat_id, "\u274c \u6570\u636e\u5e93\u4e2d\u672a\u627e\u5230\u8be5\u8282\u70b9\u7684\u901a\u8baf\u5730\u5740\u3002")
        return

    agent_ip = rows[0][0]
    agent_port = rows[0][1]

    if not agent_ip or not agent_port:
        send_msg(s_chat_id, "\u274c \u6570\u636e\u5e93\u4e2d\u672a\u627e\u5230\u8be5\u8282\u70b9\u7684\u901a\u8baf\u5730\u5740\u3002")
        return

    progress_text = f"\u23f3 \u6b63\u5728\u5411 `{target_node}` \u53d1\u9001 OTA \u89e6\u53d1\u62a5\u6587..."
    progress_btn = [[{"text": "\U0001f3e0 \u4e3b\u83dc\u5355", "callback_data": "/start"}]]
    if msg_id:
        edit_ui(s_chat_id, msg_id, progress_text, progress_btn)
    else:
        send_ui(s_chat_id, progress_text, progress_btn)

    target_url = generate_signed_url(agent_ip, agent_port, "/trigger_ota", s_chat_id)
    response = curl_agent_sync(target_url)

    if response == "FAILED":
        text_res = "\u274c OTA \u6307\u4ee4\u4e0b\u53d1\u5f7b\u5e95\u5931\u8d25\uff01\u94fe\u8def\u5f02\u5e38\u6216\u4e25\u7981\u4f7f\u7528 HTTP \u964d\u7ea7\u901a\u8baf\u3002"
    elif "403" in response:
        text_res = "\u26a0\ufe0f **\u8282\u70b9\u62d2\u7edd\u6267\u884c**\uff1a\u8be5\u8282\u70b9\u672c\u5730\u672a\u5f00\u542f OTA \u6743\u9650\u6216\u8fd0\u884c\u5728\u5b98\u65b9\u7f51\u5173\u4e0b\uff01"
    else:
        text_res = "\u2705 OTA (TLS\u52a0\u5bc6) \u89e6\u53d1\u6210\u529f\uff01\u8282\u70b9\u6b63\u5728\u540e\u53f0\u6267\u884c\u62c9\u53d6\u91cd\u6784..."

    back_btn = [[{"text": "\u2b05\ufe0f \u8fd4\u56de\u8282\u70b9\u9762\u677f", "callback_data": f"manage:{target_node}"},
                 {"text": "\U0001f3e0 \u4e3b\u83dc\u5355", "callback_data": "/start"}]]
    if msg_id:
        edit_ui(s_chat_id, msg_id, text_res, back_btn)
    else:
        send_ui(s_chat_id, text_res, back_btn)


def handle_master_ota_confirm(chat_id, msg_id=None):
    """Handle master_ota_confirm callback - show self-upgrade warning."""
    s_chat_id = sanitize_chat_id(chat_id)
    btns = [
        [{"text": "\U0001f6a8 \u786e\u8ba4\u91cd\u6784\u53f8\u4ee4\u90e8", "callback_data": "master_ota_execute"}],
        [{"text": "\u53d6\u6d88\u64cd\u4f5c", "callback_data": "/start"}],
    ]
    warning_msg = (
        "\u2622\ufe0f **\u3010\u6700\u9ad8\u6307\u4ee4\uff1a\u4e2d\u67a2\u91d1\u8749\u8131\u58f3\u3011**\n\n"
        "\u6b64\u64cd\u4f5c\u5c06\u62c9\u53d6\u6700\u65b0\u6e90\u7801\u5e76\u5f3a\u884c\u8986\u76d6\u53f8\u4ee4\u90e8\u6838\u5fc3\u8fdb\u7a0b\u3002\n\n"
        "\u26a0\ufe0f **\u98ce\u9669\u63d0\u793a**\uff1a\n"
        "\u5347\u7ea7\u671f\u95f4\u53f8\u4ee4\u90e8\u5c06\u77ed\u6682\u5931\u8054\uff08\u7ea63-5\u79d2\uff09\u3002\u5b8c\u6210\u540e\u4f1a\u81ea\u52a8\u53d1\u9001\u6377\u62a5\u3002\n\n"
        "**\u662f\u5426\u786e\u5b9a\u6267\u884c\u53f8\u4ee4\u90e8\u81ea\u6211\u5347\u7ea7\uff1f**"
    )
    if msg_id:
        edit_ui(s_chat_id, msg_id, warning_msg, btns)
    else:
        send_ui(s_chat_id, warning_msg, btns)


def handle_master_ota_execute(chat_id, msg_id=None):
    """Handle master_ota_execute callback - self-upgrade logic."""
    s_chat_id = sanitize_chat_id(chat_id)

    progress_text = "\u23f3 \u6b63\u5728\u4e0b\u8f7d\u91cd\u6784\u56fe\u7eb8\uff0c\u53f8\u4ee4\u90e8\u5373\u5c06\u8fdb\u5165\u9759\u9ed8\u91cd\u542f..."
    if msg_id:
        edit_msg(s_chat_id, msg_id, progress_text)
    else:
        send_msg(s_chat_id, progress_text)

    # Download and execute the install script
    try:
        result = subprocess.run(
            ["curl", "-fsSL", f"{REPO_RAW_URL}/master/install_master.sh", "-o", "/tmp/install_master.sh"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise Exception("Download failed")

        # Validate script syntax
        check = subprocess.run(
            ["bash", "-n", "/tmp/install_master.sh"],
            capture_output=True, text=True, timeout=10
        )
        if check.returncode != 0:
            error_text = "\u274c OTA \u4f20\u8f93\u53d7\u635f\uff1a\u811a\u672c\u4e0b\u8f7d\u4e0d\u5b8c\u6574\uff0c\u5df2\u89e6\u53d1\u9632\u7816\u7194\u65ad\uff0c\u5347\u7ea7\u53d6\u6d88\uff01"
            if msg_id:
                edit_msg(s_chat_id, msg_id, error_text)
            else:
                send_msg(s_chat_id, error_text)
            return

        subprocess.run(["chmod", "+x", "/tmp/install_master.sh"], check=True)

        env = os.environ.copy()
        env["SILENT_MASTER_OTA"] = "true"
        env["OTA_CHAT_ID"] = s_chat_id
        subprocess.Popen(
            ["bash", "/tmp/install_master.sh"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        error_text = "\u274c \u53f8\u4ee4\u90e8\u5347\u7ea7\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u7f51\u7edc\u8fde\u63a5\u3002"
        if msg_id:
            edit_msg(s_chat_id, msg_id, error_text)
        else:
            send_msg(s_chat_id, error_text)




def handle_reply_rename(chat_id, reply_to_text, text):
    """Detect and handle rename reply messages."""
    if "\u270f\ufe0f \u8bf7\u56de\u590d\u672c\u6d88\u606f\u4ee5\u91cd\u547d\u540d\u8282\u70b9:" not in reply_to_text:
        return False

    # Extract target node from the reply_to_message text
    lines = reply_to_text.split("\n")
    target_node = ""
    for line in lines:
        stripped = line.strip().replace("`", "").strip()
        if stripped and "\u270f\ufe0f" not in stripped and "\u4ec5\u9650" not in stripped:
            candidate = sanitize_node_name(stripped)
            if candidate:
                target_node = candidate
                break

    if not target_node:
        return False

    # Sanitize new alias
    new_alias = text.replace("_", "-")
    new_alias = RE_UNSAFE_CHARS.sub("", new_alias)
    new_alias = new_alias.replace(":", "")[:30]

    if not new_alias:
        return False

    handle_do_rename(chat_id, target_node, new_alias)
    return True


# ==========================================================
# Heartbeat Endpoint Handler
# ==========================================================


def handle_heartbeat(headers, body):
    """Validate HMAC signature and update node last_seen.

    Headers: X-Signature, X-Timestamp, X-Chat-Id
    Body: JSON with node_name, agent_version, public_ip, agent_port, region_code, node_alias, timestamp
    """
    signature = headers.get("X-Signature", "")
    timestamp = headers.get("X-Timestamp", "")
    req_chat_id = headers.get("X-Chat-Id", "")

    if not signature or not req_chat_id:
        return 401, {"error": "Missing signature or chat_id"}

    # Validate HMAC using chat_id as key
    # Agent signs "body:timestamp", so reconstruct the same payload
    sign_payload = body + b":" + timestamp.encode() if timestamp else body
    expected = hmac.new(
        req_chat_id.encode(), sign_payload, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        return 403, {"error": "Invalid signature"}

    try:
        data = json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 400, {"error": "Invalid JSON"}

    node_name = data.get("node_name", "")
    if not node_name:
        return 400, {"error": "Missing node_name"}

    s_chat_id = sanitize_chat_id(req_chat_id)
    s_node_name = sanitize_node_name(node_name)

    # Update last_seen for matching node
    db_exec(
        "UPDATE nodes SET last_seen=CURRENT_TIMESTAMP WHERE chat_id=? AND node_name=?;",
        (s_chat_id, s_node_name)
    )

    # Anomaly detection: high load and recent reboot alerts
    anomalies = []
    load_avg = data.get("load_avg", "")
    uptime = data.get("uptime", None)

    if load_avg:
        try:
            load_1min = float(load_avg.split(",")[0])
            if load_1min > 10.0:
                anomalies.append(f"CPU 1min 负载过高: {load_1min}")
        except (ValueError, IndexError):
            pass

    if uptime is not None:
        try:
            uptime_sec = int(uptime)
            if uptime_sec < 300:
                anomalies.append(f"节点近期重启 (运行仅 {uptime_sec} 秒)")
        except (ValueError, TypeError):
            pass

    if anomalies and req_chat_id:
        cooldown_key = (req_chat_id, s_node_name)
        now = time.time()
        last_alert = _alert_cooldowns.get(cooldown_key, 0)
        if now - last_alert >= ALERT_COOLDOWN_SECONDS:
            _alert_cooldowns[cooldown_key] = now
            node_alias = data.get("node_alias", node_name)
            alert_lines = "\n".join(f"  - {a}" for a in anomalies)
            alert_msg = (
                f"\U000026a0\U0000fe0f *节点异常告警*\n"
                f"节点: `{node_alias}` (`{node_name}`)\n"
                f"异常:\n{alert_lines}\n"
                f"负载: `{load_avg}` | 运行时间: `{uptime}s`"
            )
            send_msg(req_chat_id, alert_msg)

    return 200, {"status": "ok", "node": s_node_name}


# ==========================================================
# HTTP Server
# ==========================================================


class WebhookHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the webhook server."""

    def log_message(self, format, *args):
        """Suppress default access logging unless in DEBUG mode."""
        if DEBUG:
            print(f"[HTTP] {self.client_address[0]} {format % args}")

    def _send_json(self, status_code, data):
        """Send a JSON response."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/health" or self.path == "/":
            self._send_json(200, {"status": "ok", "version": MASTER_VERSION})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        """Handle POST requests."""
        content_length = int(self.headers.get("Content-Length", 0))

        # Reject oversized requests to prevent memory exhaustion
        if content_length > MAX_BODY_SIZE:
            self._send_json(413, {"error": "Request body too large"})
            return

        body = self.rfile.read(content_length) if content_length > 0 else b""

        if self.path == "/webhook":
            self._handle_webhook(body)
        elif self.path == "/heartbeat":
            headers = {
                "X-Signature": self.headers.get("X-Signature", ""),
                "X-Timestamp": self.headers.get("X-Timestamp", ""),
                "X-Chat-Id": self.headers.get("X-Chat-Id", ""),
            }
            status, result = handle_heartbeat(headers, body)
            self._send_json(status, result)
        else:
            self._send_json(404, {"error": "not found"})

    def _handle_webhook(self, body):
        """Process a Telegram webhook update."""
        # Verify Telegram secret token
        secret_token = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(secret_token, WEBHOOK_SECRET):
            debug_log(f"Webhook rejected: invalid secret token")
            self._send_json(403, {"error": "Invalid secret token"})
            return

        self._send_json(200, {"ok": True})

        try:
            update = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            debug_log(f"Webhook body parse failed: {e}")
            return

        debug_log(f"Webhook received update_id={update.get('update_id', '?')}")

        # Process in a separate thread to not block the response
        threading.Thread(target=self._process_update, args=(update,), daemon=True).start()

    def _process_update(self, update):
        """Route Telegram update to appropriate handler."""
        try:
            self._route_update(update)
        except Exception:
            traceback.print_exc()

    def _route_update(self, update):
        """Route update to command handlers."""
        # Extract common fields
        message = update.get("message")
        callback_query = update.get("callback_query")

        if callback_query:
            chat_id = str(callback_query.get("message", {}).get("chat", {}).get("id", ""))
            text = callback_query.get("data", "")
            cb_id = callback_query.get("id", "")
            msg_id = callback_query.get("message", {}).get("message_id")
            debug_log(f"Route: callback_query text='{text}' chat_id={chat_id}")
        elif message:
            chat_id = str(message.get("chat", {}).get("id", ""))
            text = message.get("text", "")
            cb_id = None
            msg_id = None
            debug_log(f"Route: message text='{text}' chat_id={chat_id}")
        else:
            debug_log(f"Route: unknown update type, skipping")
            return

        if not chat_id or not text:
            return

        # Handle svq (deep-sea sonar) data ingestion first
        if text.startswith("svq|"):
            handle_svq(chat_id, text, cb_id, msg_id)
            return

        # Handle reply-based rename detection
        if message and not callback_query:
            reply_to = message.get("reply_to_message", {})
            reply_text = reply_to.get("text", "") if reply_to else ""
            if reply_text and handle_reply_rename(chat_id, reply_text, text):
                return

        # Answer callback query to clear loading state
        if cb_id:
            answer_callback_query(cb_id)

        # Handle #REGISTER# messages
        if "#REGISTER#" in text:
            handle_register(chat_id, text)
            return

        # Route commands and callbacks
        if text in ("/start", "/menu"):
            handle_start_menu(chat_id, msg_id)
        elif text.startswith("/quality"):
            handle_quality_cmd(chat_id, text)
        elif text.startswith("/trend"):
            handle_trend_cmd(chat_id, text)
        elif text == "list_nodes":
            handle_list_nodes(chat_id, msg_id)
        elif text.startswith("region:"):
            region_code = text.split(":", 1)[1]
            handle_region(chat_id, region_code, msg_id)
        elif text.startswith("manage:"):
            node_name = text.split(":", 1)[1]
            handle_manage(chat_id, node_name, msg_id)
        elif text.startswith("toggle:"):
            parts = text.split(":")
            if len(parts) >= 4:
                handle_toggle(chat_id, parts[1], parts[2], parts[3], msg_id)
        elif text.startswith("del:"):
            node_name = text.split(":", 1)[1]
            handle_delete(chat_id, node_name, msg_id)
        elif text.startswith("rename:"):
            node_name = text.split(":", 1)[1]
            handle_rename_prompt(chat_id, node_name)
        elif text.startswith("do_rename:"):
            parts = text.split(":", 2)
            if len(parts) >= 3:
                handle_do_rename(chat_id, parts[1], parts[2])
        elif text.startswith("ota_confirm:"):
            node_name = text.split(":", 1)[1]
            handle_ota_confirm(chat_id, node_name, msg_id)
        elif text.startswith("ota_execute:"):
            node_name = text.split(":", 1)[1]
            handle_ota_execute(chat_id, node_name, msg_id)
        elif text == "all_run":
            handle_all_run(chat_id)
        elif text == "all_reports":
            handle_all_reports(chat_id)
        elif text == "all_ota_confirm":
            handle_all_ota_confirm(chat_id, msg_id)
        elif text == "all_ota_execute":
            handle_all_ota_execute(chat_id)
        elif text == "master_ota_confirm":
            handle_master_ota_confirm(chat_id, msg_id)
        elif text == "master_ota_execute":
            handle_master_ota_execute(chat_id, msg_id)
        elif text.startswith("trend:"):
            node_name = text.split(":", 1)[1]
            handle_trend(chat_id, node_name, msg_id)
        elif ":" in text and text.split(":")[0] in ("google", "trust", "run", "report", "log", "quality"):
            action_type = text.split(":")[0]
            node_name = text.split(":", 1)[1]
            handle_action(chat_id, action_type, node_name, msg_id)
        elif text == "ignore":
            pass  # No-op for archived report buttons




class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTP server that handles each request in a new thread."""
    daemon_threads = True
    allow_reuse_address = True


# ==========================================================
# Main Entry Point
# ==========================================================


def main():
    """Initialize DB and start the webhook HTTP server."""
    global TG_TOKEN, DB_FILE, MASTER_DIR, MASTER_VERSION
    global IS_OFFICIAL_GATEWAY, ENABLE_MASTER_OTA, WEBHOOK_URL, CHAT_ID
    global WEBHOOK_SECRET, DEBUG

    # [诊断] 无条件打印环境变量原始值
    _raw_debug = os.environ.get("DEBUG", "<MISSING>")
    print(f"[Webhook Master] Raw env: DEBUG='{_raw_debug}' (type={type(_raw_debug).__name__})")
    print(f"[Webhook Master] All env keys: {[k for k in os.environ.keys() if 'DEBUG' in k.upper() or 'debug' in k.lower()]}")

    # Reload from environment (in case of late binding)
    TG_TOKEN = os.environ.get("TG_TOKEN", TG_TOKEN)
    DB_FILE = os.environ.get("DB_FILE", DB_FILE)
    MASTER_DIR = os.environ.get("MASTER_DIR", MASTER_DIR)
    MASTER_VERSION = os.environ.get("MASTER_VERSION", MASTER_VERSION)
    IS_OFFICIAL_GATEWAY = os.environ.get("IS_OFFICIAL_GATEWAY", IS_OFFICIAL_GATEWAY)
    ENABLE_MASTER_OTA = os.environ.get("ENABLE_MASTER_OTA", ENABLE_MASTER_OTA)
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL", WEBHOOK_URL)
    CHAT_ID = os.environ.get("CHAT_ID", CHAT_ID)
    WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "") or WEBHOOK_SECRET
    DEBUG = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")

    if not TG_TOKEN:
        print("[FATAL] TG_TOKEN environment variable is not set!")
        raise SystemExit(1)

    print(f"[Webhook Master] Initializing database: {DB_FILE}")
    init_db()

    print(f"[Webhook Master] v{MASTER_VERSION} listening on 0.0.0.0:{SERVER_PORT}")
    print(f"[Webhook Master] Endpoints: POST /webhook, POST /heartbeat, GET /health")
    print(f"[Webhook Master] DEBUG={DEBUG}")
    if DEBUG:
        print(f"[Webhook Master] DEBUG MODE ENABLED - verbose logging active")
        print(f"[Webhook Master] Config: WEBHOOK_URL={WEBHOOK_URL}")
        print(f"[Webhook Master] Config: CHAT_ID={CHAT_ID}")
        print(f"[Webhook Master] Config: IS_OFFICIAL_GATEWAY={IS_OFFICIAL_GATEWAY}")
        print(f"[Webhook Master] Config: ENABLE_MASTER_OTA={ENABLE_MASTER_OTA}")

    server = ThreadedHTTPServer(("0.0.0.0", SERVER_PORT), WebhookHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Webhook Master] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
