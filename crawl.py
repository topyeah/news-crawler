# -*- coding: utf-8 -*-
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import os

# =====================【仅需修改此处】=====================
WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=e37d0ea8-21cc-4faf-a1b6-e47801d32d0d"
# 目标网站：联合早报、厦门网新闻频道
TARGET_WEBSITES = [
    {"name": "联合早报", "url": "http://www.zaobao.com/"},
    {"name": "厦门网", "url": "https://news.xmnn.cn/xmxw/"}
]
HISTORY_FILE = "history.txt"  # 存储已推送新闻链接
# =========================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9"
}

all_news = []
now = datetime.now()
# 筛选区间：北京时间 昨日00:00 ~ 今日08:00
today_8am = datetime(now.year, now.month, now.day, 8, 0, 0)
yesterday_0am = today_8am - timedelta(days=1)

def load_history() -> set:
    """读取历史已推送链接集合"""
    history = set()
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                url = line.strip()
                if url:
                    history.add(url)
    return history

def save_new_history(new_url_list: list):
    """追加新链接到历史文件"""
    if not new_url_list:
        return
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        for url in new_url_list:
            f.write(url + "\n")

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
            match = re.search(r"(\d{1,2})-(\d{1,2})", pub_str)
            if match:
                month, day = int(match.group(1)), int(match.group(2))
                pub_time = datetime(now.year, month, day)
                if yesterday_0am <= pub_time <= today_8am:
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
            match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", pub_str)
            if match:
                y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
                pub_time = datetime(y, m, d)
                if yesterday_0am <= pub_time <= today_8am:
                    news.append({"title": title, "url": link, "source": "厦门网"})
    except Exception as e:
        print("厦门网抓取异常：", str(e))
    return news

# 主逻辑
if __name__ == "__main__":
    # 加载历史链接
    history_set = load_history()
    # 抓取资讯
    for site in TARGET_WEBSITES:
        if site["name"] == "联合早报":
            res = fetch_zaobao(site["url"])
        else:
            res = fetch_xmnn(site["url"])
        all_news.extend(res)

    # 去重：过滤已经推送过的新闻
    new_news = []
    new_urls = []
    for item in all_news:
        if item["url"] not in history_set:
            new_news.append(item)
            new_urls.append(item["url"])

    # 组装消息
    if len(new_news) > 0:
        msg = f"【每日新闻汇总｜{yesterday_0am.strftime('%m-%d 00:00')} ~ {today_8am.strftime('%m-%d 08:00')}资讯】\n\n"
        for n in new_news:
            msg += f"【{n['source']}】{n['title']}\n{n['url']}\n\n"
    else:
        msg = f"【每日新闻汇总｜{yesterday_0am.strftime('%m-%d 00:00')} ~ {today_8am.strftime('%m-%d 08:00')}】未抓取到新增新闻"

    # 推送
    send_wecom_message(msg)

    # 保存本次新链接，提交回仓库实现持久化
    if new_urls:
        save_new_history(new_urls)
