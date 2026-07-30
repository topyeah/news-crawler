# -*- coding: utf-8 -*-
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json

# =====================【仅需修改此处】=====================
WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=e37d0ea8-21cc-4faf-a1b6-e47801d32d0d"
# 目标网站：联合早报、厦门网新闻频道
TARGET_WEBSITES = [
    {"name": "联合早报", "url": "http://www.zaobao.com/"},
    {"name": "厦门网", "url": "https://news.xmnn.cn/xmxw/"}
]
# 抓取24小时以内新闻
TIME_LIMIT = timedelta(hours=24)
# =========================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9"
}

all_news = []
now = datetime.now()

def send_wecom_message(content):
    """推送消息至企业微信群机器人，修复中文乱码"""
    payload = {
        "msgtype": "text",
        "text": {"content": content}
    }
    headers = {"Content-Type":"application/json;charset=utf-8"}
    res = requests.post(
        WEBHOOK_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        timeout=15
    )
    print("推送结果：", res.text)

def fetch_zaobao(url):
    """抓取联合早报新闻"""
    news = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("a.list-block")
        for item in items:
            title_tag = item.select_one(".f18")
            time_tag = item.select_one(".text-tip-color")
            if not title_tag or not time_tag:
                continue
            title = title_tag.get_text(strip=True)
            pub_str = time_tag.get_text(strip=True)
            link = item.get("href")
            if not link.startswith("http"):
                link = "https://www.zaobao.com" + link
            # 简易时间匹配（早报格式：月-日）
            match = re.search(r"(\d{1,2})-(\d{1,2})", pub_str)
            if match:
                month, day = int(match.group(1)), int(match.group(2))
                pub_time = datetime(now.year, month, day)
                if now - pub_time <= TIME_LIMIT:
                    news.append({"title": title, "url": link, "source": "联合早报"})
    except Exception as e:
        print("联合早报抓取异常：", str(e))
    return news

def fetch_xmnn(url):
    """抓取厦门网新闻"""
    news = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("li")
        for item in items:
            a_tag = item.select_one("a")
            span_time = item.select_one("span")
            if not a_tag or not span_time:
                continue
            title = a_tag.get_text(strip=True)
            pub_str = span_time.get_text(strip=True)
            link = a_tag.get("href")
            if not link:
                continue
            if not link.startswith("http"):
                link = "https://news.xmnn.cn" + link
            # 匹配 YYYY-MM-DD 标准日期
            match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", pub_str)
            if match:
                y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
                pub_time = datetime(y, m, d)
                if now - pub_time <= TIME_LIMIT:
                    news.append({"title": title, "url": link, "source": "厦门网"})
    except Exception as e:
        print("厦门网抓取异常：", str(e))
    return news

# 依次抓取两个网站
for site in TARGET_WEBSITES:
    if site["name"] == "联合早报":
        res = fetch_zaobao(site["url"])
    else:
        res = fetch_xmnn(site["url"])
    all_news.extend(res)

# 消息组装
if len(all_news) > 0:
    msg = "【每日新闻汇总｜近24小时资讯】\n\n"
    for n in all_news:
        msg += f"【{n['source']}】{n['title']}\n{n['url']}\n\n"
else:
    msg = "【每日新闻汇总】近24小时未抓取到新增新闻"

# 推送
send_wecom_message(msg)
