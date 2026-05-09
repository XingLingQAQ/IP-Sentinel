import urllib.request
import xml.etree.ElementTree as ET
import os
import json
import random

# ================== [路径防弹装甲] ==================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
REGIONS_DIR = os.path.join(PROJECT_ROOT, "data", "regions")
# ====================================================

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# 全球骨干新闻 RSS 监听矩阵
RSS_FEEDS = {
    "US": ["http://rss.cnn.com/rss/cnn_topstories.rss", "https://feeds.npr.org/1001/rss.xml"],
    "UK": ["http://feeds.bbci.co.uk/news/rss.xml"],
    "AU": ["https://www.abc.net.au/news/feed/51120/rss.xml"],
    "CA": ["https://www.cbc.ca/cmlink/rss-topstories"],
    "DE": ["https://www.tagesschau.de/xml/rss2"],
    "FR": ["https://www.france24.com/fr/rss"],
    "ES": ["https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"],
    "JP": ["https://news.yahoo.co.jp/rss/topics/top-picks.xml"],
    "HK": ["https://hk.news.yahoo.com/rss/hong-kong"],
    "MO": ["https://macaudailytimes.com.mo/feed/"],
    "TW": ["https://news.google.com/rss?hl=zh-TW&gl=TW&ceid=TW:zh-Hant"],
    "KR": ["https://www.yonhapnewstv.co.kr/category/news/headline/feed/"],
    "SG": ["https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml"],
    "NL": ["https://feeds.nos.nl/nosnieuwsalgemeen"],
    "VN": ["https://vnexpress.net/rss/tin-moi-nhat.rss"],
    "MY": ["https://news.google.com/rss?hl=en-MY&gl=MY&ceid=MY:en"],
    "NG": ["https://punchng.com/feed/", "https://www.vanguardngr.com/feed/"],
    "TR": ["https://www.hurriyet.com.tr/rss/anasayfa"],
    # ====== 下方为 PR #47 亚洲与中东新战区扩充源 (已通过实机验证) ======
    "PH": ["https://news.google.com/rss?hl=en-PH&gl=PH"],
    "TH": ["https://www.bangkokpost.com/rss/data/topstories.xml"],
    "ID": ["https://www.antaranews.com/rss/terkini.xml"],
    "IN": ["https://timesofindia.indiatimes.com/rssfeedstopstories.cms"],
    "AE": ["https://news.google.com/rss?hl=en-AE&gl=AE"],
    "SA": ["https://news.google.com/rss?hl=ar-SA&gl=SA"],
    "BD": ["https://www.thedailystar.net/frontpage/rss.xml"],
    "NP": ["https://news.google.com/rss?hl=en-NP&gl=NP"],
    "KH": ["https://www.cambodiadaily.com/feed/"],
    "MM": ["https://news.google.com/rss?hl=en-MM&gl=MM"],
    "LA": ["https://news.google.com/rss?hl=en-LA&gl=LA"],
    "MN": ["https://news.google.com/rss?hl=en-MN&gl=MN"]
}

def fetch_rss_links(region_code, max_items=15):
    """抓取该战区最新的 RSS 新闻链接"""
    feeds = RSS_FEEDS.get(region_code, [])
    if not feeds:
        return []
    
    links = []
    for url in feeds:
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10) as response:
                xml_data = response.read()
                root = ET.fromstring(xml_data)
                for item in root.findall('.//item'):
                    link = item.find('link')
                    if link is not None and link.text:
                        clean_link = link.text.strip()
                        if clean_link.startswith('http'):
                            links.append(clean_link)
        except Exception as e:
            print(f"⚠️ [{region_code}] RSS 抓取异常 ({url}): {e}")
            
    # 去重并截取最新
    return list(set(links))[:max_items]

def process_json_file(file_path, region_code):
    """融合静态基石与动态新闻"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        trust_mod = data.get("trust_module", {})
        if not trust_mod or "static_urls" not in trust_mod:
            return
            
        static_urls = trust_mod.get("static_urls", [])
        
        # 抓取今日该战区的活体新闻流
        daily_news_urls = fetch_rss_links(region_code)
        
        # 战术混合：基石(保证高权重) + 新闻(保证活体动态)
        combined_urls = static_urls + daily_news_urls
        
        # 深度洗牌，打破机械顺序特征
        combined_urls = list(set(combined_urls))
        random.shuffle(combined_urls)
        
        # 覆写回供 Agent 拉取的 white_urls
        trust_mod["white_urls"] = combined_urls
        data["trust_module"] = trust_mod
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        print(f"✅ [信用融合] {os.path.basename(file_path)}: 骨干 {len(static_urls)} 条 + 活体 {len(daily_news_urls)} 条")
        
    except Exception as e:
        print(f"❌ [处理失败] {file_path}: {e}")

if __name__ == '__main__':
    print("========== 启动 IP-Sentinel 活体新闻流融合引擎 ==========")
    for root_dir, _, files in os.walk(REGIONS_DIR):
        for file in files:
            if file.endswith(".json"):
                file_path = os.path.join(root_dir, file)
                region_code = os.path.relpath(file_path, REGIONS_DIR).split(os.sep)[0]
                process_json_file(file_path, region_code)
    print("========== 融合引擎执行完毕 ==========")
