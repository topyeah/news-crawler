# -*- coding: utf-8 -*-
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os

# =====================【自行修改】=====================
WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=e37d0ea8-21cc-4faf-a1b6-e47801d32d0d"
HISTORY_FILE = "history.txt"
MAX_CRAWL = 12
# =====================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Connection": "keep-alive"
}

def load_history() -> set:
    history = set()
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                url = line.strip()
                if url:
                    history.add(url)
        print(f"【加载历史记录】一共 {len(history)} 条已推送链接")
    else:
        print("【加载历史记录】history.txt 不存在，历史为空")
    return history

def save_new_history(new_url_list: list):
    if not new_url_list:
        return
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        for url in new_url_list:
            f.write(url + "\n")
    print(f"【保存记录】新增 {len(new_url_list)} 条链接写入history")

def send_wecom_message(content):
    payload = {
        "msgtype": "text",
        "text": {"content": content}
    }
    headers = {"Content-Type":"application/json;charset=utf-8"}
    try:
        res = requests.post(
            WEBHOOK_URL,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            timeout=15
        )
        print("推送返回：", res.text)
    except Exception as e:
        print("推送失败：", str(e))

def get_article_summary(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        soup = BeautifulSoup(resp.text, "html.parser")
        summary_tag = soup.find("p", class_="article-lead")
        if summary_tag:
            summary = summary_tag.get_text(strip=True)
            if len(summary) > 160:
                summary = summary[:160] + "……"
            return summary
        return "无摘要"
    except Exception as e:
        print(f"获取摘要失败 {url}: {e}")
        return "摘要获取失败"

def crawl_zaobao():
    base_url = "https://www.zaobao.com.sg"
    target_url = "https://www.zaobao.com.sg/news/china"
    news_list = []
    try:
        resp = requests.get(target_url, headers=HEADERS, timeout=15)
        print(f"页面请求状态码：{resp.status_code}")
        soup = BeautifulSoup(resp.text, "html.parser")
        all_a = soup.find_all("a")
        print(f"页面一共找到<a>标签数量：{len(all_a)}")
        temp_links = []
        for a in all_a:
            title = a.get_text(strip=True)
            href = a.get("href","")
            if len(title) > 12 and "/story/" in href:
                if not href.startswith("http"):
                    href = base_url + href
                temp_links.append({"title": title, "url": href})
        print(f"筛选出带/story/的链接数量：{len(temp_links)}")

        seen = set()
        for item in temp_links:
            if item["url"] not in seen and len(news_list) < MAX_CRAWL:
                seen.add(item["url"])
                summary = get_article_summary(item["url"])
                item["summary"] = summary
                item["source"] = "联合早报"
                news_list.append(item)
        print(f"最终组装完成新闻条数：{len(news_list)}")
    except Exception as e:
        print("联合早报抓取异常：", str(e))
    return news_list

if __name__ == "__main__":
    history_set = load_history()
    raw_news = crawl_zaobao()

    new_news = []
    new_urls = []
    for item in raw_news:
        if item["url"] not in history_set:
            new_news.append(item)
            new_urls.append(item["url"])
    print(f"过滤历史后，待推送新增新闻：{len(new_news)} 条")

    time_now = datetime.now().strftime("%m-%d")
    if len(new_news) > 0:
        msg = f"【联合早报·中国新闻汇总】{time_now}\n\n"
        for n in new_news:
            block = f"【{n['title']}】\n{n['summary']}\n{n['url']}\n\n"
            if len(msg + block) > 1900:
                msg += "内容较多，剩余新闻省略"
                break
            msg += block
    else:
        msg = f"【联合早报·中国新闻汇总】{time_now}\n暂无新增新闻"

    send_wecom_message(msg)
    save_new_history(new_urls)
