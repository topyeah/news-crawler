# -*- coding: utf-8 -*-
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import os
import time

# =====================【自行修改配置区】=====================
WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=e37d0ea8-21cc-4faf-a1b6-e47801d32d0d"
HISTORY_FILE = "history.txt"
MAX_CRAWL = 20
PAGE_TIMEOUT = 6
TOTAL_RUN_SECONDS = 220
MAX_SUMMARY_LEN = 300
MIN_PARAGRAPH_LEN = 40
NEWS_VALID_DAYS = 7
SAFE_MSG_LIMIT = 1600
HISTORY_KEEP_DAYS = 7
# ===========================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Connection": "keep-alive"
}
start_time = time.time()

def is_timeout():
    return time.time() - start_time > TOTAL_RUN_SECONDS

def load_history() -> dict:
    history = {}
    cutoff = datetime.now() - timedelta(days=HISTORY_KEEP_DAYS)
    if os.path.exists(HISTORY_FILE):
        keep_lines = []
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if "|||" in line:
                    url, dt_str = line.split("|||", 1)
                    try:
                        pub_dt = datetime.fromisoformat(dt_str)
                        if pub_dt >= cutoff:
                            history[url] = pub_dt
                            keep_lines.append(line)
                    except Exception:
                        history[url] = None
                        keep_lines.append(line)
                else:
                    url = line
                    history[url] = None
                    keep_lines.append(line)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            for l in keep_lines:
                f.write(l + "\n")
        print(f"【加载历史记录】清洗完成，有效记录 {len(history)} 条")
    else:
        print("【加载历史记录】history.txt 不存在，首次运行")
    return history

def save_new_history(new_items: list):
    if not new_items:
        return
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        for url, pub_dt in new_items:
            if pub_dt is not None:
                line = f"{url}|||{pub_dt.isoformat()}"
            else:
                line = url
            f.write(line + "\n")
    print(f"【保存记录】新增 {len(new_items)} 条链接写入history")

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
            timeout=10
        )
        print(f"【推送HTTP状态码】{res.status_code}")
        print("【推送返回】", res.text)
        time.sleep(0.6)
    except Exception as e:
        print("【推送异常】", str(e))

def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def parse_news_datetime(soup):
    meta_time = soup.find("meta", property="article:published_time")
    if meta_time and meta_time.get("content"):
        try:
            dt_str = meta_time["content"].strip()
            pure_dt_str = dt_str.replace("Z","").split("+")[0]
            pub_dt = datetime.fromisoformat(pure_dt_str)
            return pub_dt
        except Exception:
            return None
    return None

def get_article_summary(url):
    if is_timeout():
        return "脚本整体超时，放弃获取摘要", None
    try:
        resp = requests.get(url, headers=HEADERS, timeout=PAGE_TIMEOUT)
        soup = BeautifulSoup(resp.text, "html.parser")
        pub_datetime = parse_news_datetime(soup)

        meta_desc = soup.find("meta", attrs={"name":"description"})
        if meta_desc and meta_desc.get("content"):
            summary = clean_text(meta_desc["content"])
            if len(summary) > MAX_SUMMARY_LEN:
                summary = summary[:MAX_SUMMARY_LEN] + "……"
            return summary, pub_datetime

        content_text = ""
        all_p = soup.find_all("p")
        for p in all_p:
            para = clean_text(p.get_text())
            if len(para) >= MIN_PARAGRAPH_LEN:
                content_text += para + " "
                if len(content_text) >= MAX_SUMMARY_LEN + 100:
                    break
        if len(content_text) > 20:
            if len(content_text) > MAX_SUMMARY_LEN:
                content_text = content_text[:MAX_SUMMARY_LEN] + "……"
            return content_text, pub_datetime

        return "无摘要", pub_datetime
    except Exception as e:
        print(f"【详情页访问失败】{url} 错误:{str(e)}")
        return "摘要获取失败", None

def crawl_zaobao():
    base_url = "https://www.zaobao.com.sg"
    target_url = "https://www.zaobao.com.sg/news/china"
    news_list = []
    try:
        resp = requests.get(target_url, headers=HEADERS, timeout=8)
        print(f"首页请求状态码：{resp.status_code}")
        soup = BeautifulSoup(resp.text, "html.parser")
        all_a = soup.find_all("a")
        print(f"页面共找到<a>标签：{len(all_a)}")
        temp_links = []
        seen_link = set()
        for a in all_a:
            title = clean_text(a.get_text())
            href = a.get("href","")
            if len(title) >= 15 and href.startswith("/") and href not in seen_link:
                seen_link.add(href)
                full_url = base_url + href
                temp_links.append({"title": title, "url": full_url})
        print(f"初步筛选候选链接数量：{len(temp_links)}")

        seen = set()
        deadline = datetime.now() - timedelta(days=NEWS_VALID_DAYS)
        for idx, item in enumerate(temp_links):
            if is_timeout():
                print("【警告】全局运行超时，停止抓取新闻详情")
                break
            if item["url"] not in seen and len(news_list) < MAX_CRAWL:
                seen.add(item["url"])
                print(f"正在抓取第{idx+1}条详情：{item['url']}")
                summary, pub_time = get_article_summary(item["url"])
                if pub_time is not None and pub_time < deadline:
                    print(f"新闻超出时效，舍弃 {item['url']}")
                    continue
                item["summary"] = summary
                item["pubtime"] = pub_time
                news_list.append(item)
                time.sleep(0.3)
        print(f"====抓取完成！经过时效筛选后，有效新闻条数：{len(news_list)}====")
    except Exception as e:
        print("首页抓取异常：", str(e))
    return news_list

if __name__ == "__main__":
    history_dict = load_history()
    raw_news = crawl_zaobao()

    new_news = []
    save_items = []
    for item in raw_news:
        url = item["url"]
        if url not in history_dict:
            new_news.append(item)
            save_items.append((url, item["pubtime"]))
    print(f"过滤历史推送记录，待推送新增新闻：{len(new_news)} 条")

    new_news.sort(key=lambda x: x["pubtime"] if x["pubtime"] is not None else datetime.min, reverse=True)

    time_now = datetime.now().strftime("%m-%d")
    header = f"【联合早报·中国新闻汇总】{time_now}\n\n"

    print("====开始执行消息推送====")
    if len(new_news) > 0:
        batch_msg = header
        for n in new_news:
            block = f"{n['summary']}\n{n['url']}\n\n"
            if len(batch_msg + block) > SAFE_MSG_LIMIT:
                send_wecom_message(batch_msg)
                batch_msg = header
            batch_msg += block
        send_wecom_message(batch_msg)
    else:
        send_wecom_message(f"【联合早报·中国新闻汇总】{time_now}\n暂无新增新闻")
    print("====推送全部完成====")

    save_new_history(save_items)
