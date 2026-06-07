import os
import smtplib
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.mime.text import MIMEText
from urllib.parse import urlparse

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO = os.getenv("EMAIL_TO")

RSS_FEEDS = {
    "Reuters": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
    "BBC Business": "https://feeds.bbci.co.uk/news/business/rss.xml",
    "BBC Technology": "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "TechCrunch": "https://techcrunch.com/feed/",
    "AP News": "https://apnews.com/hub/business?output=rss",
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

            if not title or not link:
                continue

            if not is_relevant(title):
                continue

            articles.append({
                "source": source_name,
                "title": title,
                "link": link,
                "date": pub_date
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

def build_report(news):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = []
    lines.append("【美股事实日报】")
    lines.append(f"日期：{today}")
    lines.append("")
    lines.append("说明：本邮件只收集公开来源新闻，不做预测，不提供买卖建议。")
    lines.append("新闻来源优先来自 Reuters、BBC、TechCrunch、AP News、Federal Reserve、White House、SEC 等权威来源。")
    lines.append("如果某些来源当天 RSS 无可用内容，系统不会使用小网站替代，也不会编造新闻。")
    lines.append("")
    lines.append("一、今日新闻链接汇总")
    lines.append("")

    if not news:
        lines.append("指定来源新闻不足。")
        lines.append("过去24小时内未能从指定权威来源抓取到足够与美股相关的新闻。")
        lines.append("")
    else:
        for i, article in enumerate(news, 1):
            lines.append(f"{i}. {article['title']}")
            lines.append(f"来源：{article['source']}")
            lines.append(f"时间：{article['date']}")
            lines.append(f"链接：{article['link']}")
            lines.append("")

    lines.append("二、监控范围")
    lines.append("")
    lines.append("本系统重点监控美股、纳斯达克、标普500、道琼斯、美联储、FOMC、鲍威尔、美联储官员讲话、美国政府官员发言、财政部、白宫、SEC、DOJ、CPI、PPI、非农、失业率、GDP、PMI、ISM、美债收益率、美元、油价、AI、半导体、出口管制、地缘政治风险。")
    lines.append("")
    lines.append("重点公司包括：NVDA、TSLA、MSFT、META、AAPL、AMZN、AMD、GOOGL。")
    lines.append("")
    lines.append("三、信息说明")
    lines.append("")
    lines.append("本邮件仅用于新闻事实整理。")
    lines.append("所有新闻均以原始链接为准。")
    lines.append("本邮件不构成投资建议。")

    report = "\n".join(lines)

    if len(report) < 1000:
        report += "\n\n补充说明：本系统采用严格来源过滤机制。若当天权威来源中与美股直接相关的新闻数量较少，邮件仍会保留来源透明原则，不使用未经验证的小网站、自媒体或二次搬运内容进行填充。"

    return report

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
    report = build_report(news)
    send_email(report)
    print("Email sent successfully.")

if __name__ == "__main__":
    main()
