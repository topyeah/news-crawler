# -*- coding: utf-8 -*-
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json

# =====================【仅需修改此处】=====================
WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=e37d0ea8-21cc-4faf-a1b6-e47801d32d0d"
TARGET_WEBSITES = [
    {"name": "联合早报", "url": "https://www.zaobao.com/"},
    {"name": "厦门网", "url": "https://news.xmnn.cn/xmxw/"}
]
# =========================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9"
}

def send_wecom_message(content):
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
    print("推送接口返回：", res.text)

def test_zaobao():
    print("=====开始测试联合早报=====")
    try:
        resp = requests.get("https://www.zaobao.com/", headers=HEADERS, timeout=15)
        print("状态码:", resp.status_code)
        soup = BeautifulSoup(resp.text, "html.parser")
        # 原选择器失效，打印全部链接排查
        all_a = soup.find_all("a")
        print(f"页面所有a标签总数：{len(all_a)}")
        news_list = []
        for a in all_a[:80]:
            title = a.get_text(strip=True)
            href = a.get("href","")
            if len(title) > 10 and ("story" in href or "/news/" in href):
                news_list.append({"title":title,"url":href})
        print(f"筛选出疑似新闻链接数量：{len(news_list)}")
        for item in news_list[:10]:
            print(item)
        return news_list
    except Exception as e:
        print("联合早报异常：", str(e))
        return []

def test_xmnn():
    print("=====开始测试厦门网=====")
    try:
        resp = requests.get("https://news.xmnn.cn/xmxw/", headers=HEADERS, timeout=15)
        print("状态码:", resp.status_code)
        soup = BeautifulSoup(resp.text, "html.parser")
        all_li = soup.find_all("li")
        print(f"页面li标签总数：{len(all_li)}")
        news_list = []
        for li in all_li:
            a = li.find("a")
            if a:
                title = a.get_text(strip=True)
                href = a.get("href","")
                if len(title) > 8:
                    if not href.startswith("http"):
                        href = "https://news.xmnn.cn" + href
                    news_list.append({"title": title, "url": href})
        print(f"筛选新闻条目数量：{len(news_list)}")
        for item in news_list[:10]:
            print(item)
        return news_list
    except Exception as e:
        print("厦门网异常：", str(e))
        return []

if __name__ == "__main__":
    zb_news = test_zaobao()
    xm_news = test_xmnn()
    all_raw = zb_news + xm_news

    if len(all_raw) > 0:
        msg = f"【测试汇总】一共抓取到{len(all_raw)}条新闻\n"
        for item in all_raw[:15]:
            msg += f"{item['title']}\n{item['url']}\n\n"
    else:
        msg = "【测试汇总】两个网站均未抓取到新闻"
    send_wecom_message(msg)
