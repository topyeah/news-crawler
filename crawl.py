# -*- coding: utf-8 -*-
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import os
import time
import traceback
import cchardet

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
RETRY_TIMES = 2

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}
start_time = time.time()

def is_timeout():
    return time.time() - start_time > TOTAL_RUN_SECONDS

def send_wecom(content):
    payload = {"msgtype":"text","text":{"content":content}}
    try:
        res = requests.post(WEBHOOK_URL, data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
                            headers={"Content-Type":"application/json"}, timeout=10)
        print("推送结果:",res.status_code,res.text)
        time.sleep(0.6)
    except Exception as e:
        print("推送异常",str(e))

def load_history():
    history = {}
    cutoff = datetime.now() - timedelta(days=HISTORY_KEEP_DAYS)
    if os.path.exists(HISTORY_FILE):
        keep_lines = []
        with open(HISTORY_FILE,"r",encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if "|||" in line:
                    url,dt_str = line.split("|||",1)
                    try:
                        pub_dt = datetime.fromisoformat(dt_str)
                        if pub_dt >= cutoff:
                            history[url] = pub_dt
                            keep_lines.append(line)
                    except:
                        history[url] = None
                        keep_lines.append(line)
                else:
                    history[line] = None
                    keep_lines.append(line)
        with open(HISTORY_FILE,"w",encoding="utf-8") as f:
            for l in keep_lines:
                f.write(l+"\n")
    print(f"历史记录加载完成，数量:{len(history)}")
    return history

def save_new_history(new_items):
    if not new_items:
        return
    with open(HISTORY_FILE,"a",encoding="utf-8") as f:
        for url,pub_dt in new_items:
            if pub_dt:
                f.write(f"{url}|||{pub_dt.isoformat()}\n")
            else:
                f.write(url+"\n")
    print(f"新增记录写入:{len(new_items)}条")

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r"\s+"," ",text.strip())
    # 过滤不可见特殊字符，减少乱码展示
    text = re.sub(r"[\x00-\x1F\x7F]", "", text)
    return text

def parse_pubtime(soup):
    tag = soup.find("meta",property="article:published_time")
    if not tag:
        return None
    try:
        s = tag["content"].strip().replace("Z","").split("+")[0]
        return datetime.fromisoformat(s)
    except:
        return None

def get_detail(url):
    if is_timeout():
        return "", None
    summary = ""
    pub_time = None
    for attempt in range(RETRY_TIMES + 1):
        try:
            r = requests.get(url,headers=HEADERS,timeout=PAGE_TIMEOUT)
            # 自动识别页面编码，解决乱码核心方案
            encoding_info = cchardet.detect(r.content)
            encode = encoding_info["encoding"]
            if encode:
                r.encoding = encode
            soup = BeautifulSoup(r.text,"html.parser")
            pub_time = parse_pubtime(soup)
            # 优先og摘要
            og_desc = soup.find("meta", property="og:description")
            if og_desc:
                summary = clean_text(og_desc["content"])
            # 其次description
            if not summary:
                meta_desc = soup.find("meta", name="description")
                if meta_desc:
                    summary = clean_text(meta_desc["content"])
            if len(summary) > MAX_SUMMARY_LEN:
                summary = summary[:MAX_SUMMARY_LEN]+"……"
            break
        except Exception as e:
            print(f"抓取尝试{attempt+1}失败 {url}：{str(e)}")
            time.sleep(0.5)
    return summary, pub_time

def crawl():
    base = "https://www.zaobao.com.sg"
    target = "https://www.zaobao.com.sg/news/china"
    news = []
    try:
        r = requests.get(target,headers=HEADERS,timeout=8)
        encoding_info = cchardet.detect(r.content)
        if encoding_info["encoding"]:
            r.encoding = encoding_info["encoding"]
        soup = BeautifulSoup(r.text,"html.parser")
        links_set = set()
        links = []
        for a in soup.find_all("a"):
            href = a.get("href","")
            title = clean_text(a.get_text())
            if len(title)>=15 and href.startswith("/") and href not in links_set:
                links_set.add(href)
                links.append(base+href)
        print("首页候选链接数量:",len(links))
        deadline = datetime.now() - timedelta(days=NEWS_VALID_DAYS)
        collected = set()
        for idx,url in enumerate(links):
            if len(news)>=MAX_CRAWL or is_timeout():
                break
            if url in collected:
                continue
            collected.add(url)
            print(f"抓取{idx+1}:{url}")
            summary,pt = get_detail(url)
            if pt and pt < deadline:
                print("新闻过期，跳过")
                continue
            news.append({"url":url,"summary":summary,"pubtime":pt})
            time.sleep(0.3)
    except Exception as e:
        print("首页抓取失败",str(e))
    print("有效新闻总数:",len(news))
    return news

def main():
    history = load_history()
    raw = crawl()
    new_list = []
    save_list = []
    for item in raw:
        if item["url"] not in history:
            new_list.append(item)
            save_list.append((item["url"],item["pubtime"]))
    print("本轮新增新闻数量:",len(new_list))
    new_list.sort(key=lambda x:x["pubtime"] if x["pubtime"] else datetime.min,reverse=True)
    header = f"【联合早报·中国新闻汇总】{datetime.now().strftime('%m-%d')}\n\n"
    if new_list:
        batch = header
        for n in new_list:
            block = ""
            if n["summary"]:
                block += f"{n['summary']}\n"
            block += f"{n['url']}\n\n"
            if len(batch+block) > SAFE_MSG_LIMIT:
                send_wecom(batch)
                batch = header
            batch += block
        send_wecom(batch)
    else:
        send_wecom(f"{header}暂无新增新闻")
    save_new_history(save_list)

if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        err_info = traceback.format_exc()
        alert_msg = f"⚠️联合早报爬虫运行异常！\n时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n错误信息：{str(err)}\n详情：{err_info[:800]}"
        send_wecom(alert_msg)
        raise
