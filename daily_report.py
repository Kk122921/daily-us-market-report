import os
import smtplib
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.mime.text import MIMEText
import google.generativeai as genai

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO = os.getenv("EMAIL_TO")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

RSS_FEEDS = {
    "BBC Business": "https://feeds.bbci.co.uk/news/business/rss.xml",
    "BBC Technology": "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "TechCrunch": "https://techcrunch.com/feed/",
    "AP News Business": "https://apnews.com/hub/business?output=rss",
    "Federal Reserve": "https://www.federalreserve.gov/feeds/press_all.xml",
    "White House": "https://www.whitehouse.gov/feed/",
    "SEC": "https://www.sec.gov/news/pressreleases.rss",
}

KEYWORDS = [
    "stock", "stocks", "nasdaq", "s&p", "dow", "market", "wall street",
    "federal reserve", "fed", "powell", "fomc", "interest rate", "inflation",
    "cpi", "ppi", "jobs", "employment", "treasury", "bond", "yield",
    "dollar", "oil", "ai", "chip", "semiconductor", "nvidia", "tesla",
    "microsoft", "meta", "apple", "amazon", "amd", "google", "alphabet",
    "sec", "doj", "white house", "tariff", "sanction", "export control"
]

def is_relevant(title):
    text = title.lower()
    return any(k.lower() in text for k in KEYWORDS)

def fetch_rss(source_name, feed_url):
    articles = []

    try:
        r = requests.get(
            feed_url,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        if r.status_code != 200:
            print(f"{source_name} RSS failed: {r.status_code}")
            return []

        root = ET.fromstring(r.content)

        for item in root.findall(".//item"):
            title = item.findtext("title", default="").strip()
            link = item.findtext("link", default="").strip()
            pub_date = item.findtext("pubDate", default="").strip()
            description = item.findtext("description", default="").strip()

            if not title or not link:
                continue

            if not is_relevant(title + " " + description):
                continue

            articles.append({
                "source": source_name,
                "title": title,
                "link": link,
                "date": pub_date,
                "description": description
            })

        return articles

    except Exception as e:
        print(f"{source_name} error:", str(e))
        return []

def collect_news():
    all_articles = []
    seen = set()

    for source, url in RSS_FEEDS.items():
        articles = fetch_rss(source, url)

        for article in articles:
            key = article["title"].lower()[:100]
            if key in seen:
                continue

            seen.add(key)
            all_articles.append(article)

    return all_articles[:30]

def build_raw_news_text(news):
    if not news:
        return "指定来源新闻不足。"

    lines = []
    for i, article in enumerate(news, 1):
        lines.append(
            f"{i}. 标题：{article['title']}\n"
            f"来源：{article['source']}\n"
            f"时间：{article['date']}\n"
            f"摘要：{article['description']}\n"
            f"链接：{article['link']}\n"
        )
    return "\n".join(lines)

def fallback_report(news_text):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return f"""
【美股事实日报】
日期：{today}

说明：本邮件只整理公开来源新闻，不做预测，不提供买卖建议。

一、原始新闻链接汇总

{news_text}

二、监控范围

本系统重点监控美股、纳斯达克、标普500、道琼斯、美联储、FOMC、鲍威尔、美联储官员讲话、美国政府官员发言、财政部、白宫、SEC、DOJ、CPI、PPI、非农、失业率、GDP、PMI、ISM、美债收益率、美元、油价、AI、半导体、出口管制、地缘政治风险。

重点公司包括：NVDA、TSLA、MSFT、META、AAPL、AMZN、AMD、GOOGL。

三、信息说明

由于 Gemini 免费额度可能出现临时限流，本次邮件使用备用格式发送。
所有新闻均以原始链接为准。
本邮件不构成投资建议。
"""

def generate_ai_report(news_text):
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        prompt = f"""
你是一名严格遵守事实的美股信息整理员。

请只根据以下新闻列表，生成中文《美股事实日报》。

要求：
1. 只基于提供的新闻，不允许编造。
2. 不做预测，不判断涨跌。
3. 不给买入、卖出、持有建议。
4. 每条重要新闻必须附带原始链接。
5. 全文必须超过1000个中文字符。
6. 如果新闻不足，明确写“指定来源新闻不足”。
7. 结构清晰，适合邮件阅读。

报告结构：

【美股事实日报】
日期：{today}

一、今日重点摘要
二、美联储与美国政府动态
三、宏观经济与美债美元
四、AI、科技与半导体
五、重点公司新闻
六、监管、地缘政治与风险事件
七、原始新闻链接汇总
八、信息说明

说明：本邮件仅用于新闻事实整理，不构成投资建议。

新闻列表：

{news_text}
"""

        for _ in range(2):
            try:
                response = model.generate_content(prompt)
                return response.text
            except Exception as e:
                print("Gemini failed, retrying:", str(e))
                time.sleep(60)

        return fallback_report(news_text)

    except Exception as e:
        print("Gemini failed completely:", str(e))
        return fallback_report(news_text)

def send_email(report):
    msg = MIMEText(report, "plain", "utf-8")
    msg["Subject"] = "美股事实日报"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

def main():
    news = collect_news()
    news_text = build_raw_news_text(news)
    report = generate_ai_report(news_text)
    send_email(report)
    print("Email sent successfully.")

if __name__ == "__main__":
    main()
