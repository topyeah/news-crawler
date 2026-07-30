# -*- coding: utf-8 -*-
import requests
import re
from bs4 import BeautifulSoup
import json

# =====================【仅需修改此处】=====================
WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=e37d0ea8-21cc-4faf-a1b6-e47801d32d0d"
# =========================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Referer": "https://www.zaobao.com.sg/"
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
    """联合早报 中国新闻栏目"""
    print("=====开始测试联合早报【中国新闻】=====")
    base_url = "https://www.zaobao.com.sg"
    target_url = "https://www.zaobao.com.sg/news/china"
    news_list = []
    try:
        resp = requests.get(target_url, headers=HEADERS, timeout=15)
        print("早报状态码:", resp.status_code)
        soup = BeautifulSoup(resp.text, "html.parser")
        all_a = soup.find_all("a")
        print(f"页面a标签总数：{len(all_a)}")
        for a in all_a:
            title = a.get_text(strip=True)
            href = a.get("href","")
            # 筛选新闻链接
            if len(title) > 12 and ("/story/" in href or "/news/" in href):
                if not href.startswith("http"):
                    href = base_url + href
                news_list.append({"source":"联合早报","title":title,"url":href})
        print(f"早报有效新闻数量：{len(news_list)}")
    except Exception as e:
        print("联合早报异常：", str(e))
    return news_list

def test_xmnn():
    """厦门网"""
    print("=====开始测试厦门网=====")
    base_url = "https://news.xmnn.cn"
    news_list = []
    try:
        session = requests.Session()
        resp = session.get(f"{base_url}/xmxw/", headers=HEADERS, timeout=20)
        print("厦门网状态码:", resp.status_code)
        if resp.status_code == 403:
            print("警告：厦门网返回403，服务器IP被拦截！")
            return news_list

        resp.encoding = "gbk"
        soup = BeautifulSoup(resp.text, "html.parser")
        all_li = soup.find_all("li")
        print(f"页面li标签总数：{len(all_li)}")
        for li in all_li:
            a = li.find("a")
            if not a:
                continue
            title = a.get_text(strip=True)
            href = a.get("href","")
            if len(title) > 8:
                if not href.startswith("http"):
                    href = base_url + href
                news_list.append({"source":"厦门网","title": title, "url": href})
        print(f"厦门网有效新闻数量：{len(news_list)}")
    except Exception as e:
        print("厦门网异常：", str(e))
    return news_list

if __name__ == "__main__":
    zb_news = test_zaobao()
    xm_news = test_xmnn()
    all_raw = zb_news + xm_news

    if len(all_raw) > 0:
        msg = f"【测试汇总】一共抓取到{len(all_raw)}条新闻\n\n"
        for item in all_raw[:15]:
            msg += f"【{item['source']}】{item['title']}\n{item['url']}\n\n"
    else:
        msg = "【测试汇总】两个网站均未抓取到新闻"
    send_wecom_message(msg)
