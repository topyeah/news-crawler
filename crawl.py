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
MAX_CRAWL = 40        # 【重点】上调最大抓取新闻数量，按需修改
PAGE_TIMEOUT = 12
TOTAL_RUN_SECONDS = 240
MAX_SUMMARY_LEN = 300
MIN_PARAGRAPH_LEN = 40
NEWS_VALID_DAYS = 7  # 只抓取7天内新闻
SAFE_MSG_LIMIT = 1600  # 单条消息字符上限
# ===========================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Connection": "keep-alive"
}
start_time = time.time()

def is_timeout():
    return time.time() - start_time > TOTAL_RUN_SECONDS

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
        print("【加载历史记录】history.txt 不存在")
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
        print(f"【推送HTTP状态码】{res.status_code}")
        print("【推送返回】", res.text)
        # 多条推送间隔0.8秒，防止风控
        time.sleep(0.8)
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
        except Exception as e:
            print("时间解析异常:", e)
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
        print(f"获取摘要失败 {url}: {str(e)}")
        return "摘要获取失败", None

def crawl_zaobao():
    base_url = "https://www.zaobao.com.sg"
    target_url = "https://www.zaobao.com.sg/news/china"
    news_list = []
    try:
        resp = requests.get(target_url, headers=HEADERS, timeout=PAGE_TIMEOUT)
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
        for item in temp_links:
            if is_timeout():
                print("【警告】运行超时，停止继续抓取")
                break
            # 这里使用MAX_CRAWL控制总量
            if item["url"] not in seen and len(news_list) < MAX_CRAWL:
                seen.add(item["url"])
                summary, pub_time = get_article_summary(item["url"])
                if pub_time is not None and pub_time < deadline:
                    print(f"新闻超出时效，舍弃 {item['url']} 发布时间:{pub_time}")
                    time.sleep(0.4)
                    continue
                item["summary"] = summary
                item["pubtime"] = pub_time
                news_list.append(item)
                time.sleep(0.4)
        print(f"经过时效筛选后，有效新闻条数：{len(news_list)}")
    except Exception as e:
        print("首页抓取异常：", str(e))
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
    print(f"过滤历史推送记录，待推送新增新闻：{len(new_news)} 条")

    # 按发布时间从新到旧排序
    new_news.sort(key=lambda x: x["pubtime"] if x["pubtime"] is not None else datetime.min, reverse=True)

    time_now = datetime.now().strftime("%m-%d")
    header = f"【联合早报·中国新闻汇总】{time_now}\n\n"

    if len(new_news) > 0:
        batch_msg = header
        for n in new_news:
            # 移除发布时间，仅保留摘要+链接
            block = f"{n['summary']}\n{n['url']}\n\n"
            # 判断追加后是否超限，超限先发送当前批次，新建消息
            if len(batch_msg + block) > SAFE_MSG_LIMIT:
                send_wecom_message(batch_msg)
                batch_msg = header
            batch_msg += block
        # 发送最后剩余批次
        send_wecom_message(batch_msg)
    else:
        send_wecom_message(f"【联合早报·中国新闻汇总】{time_now}\n暂无新增新闻")

    save_new_history(new_urls)
