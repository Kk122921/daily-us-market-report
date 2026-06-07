import os
import smtplib
import time
import requests
from datetime import datetime, timezone
from email.mime.text import MIMEText
from urllib.parse import urlparse
import google.generativeai as genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO = os.getenv("EMAIL_TO")

ALLOWED_DOMAINS = [
    "reuters.com",
    "bloomberg.com",
    "ft.com",
    "bbc.com",
    "techcrunch.com",
    "36kr.com",
    "huxiu.com",
    "apnews.com",
    "federalreserve.gov",
    "whitehouse.gov",
    "treasury.gov",
    "commerce.gov",
    "sec.gov",
    "justice.gov"
]

KEYWORDS = """
US stock market OR Nasdaq OR Federal Reserve OR Nvidia OR Tesla OR Microsoft OR AI chips
"""

def domain_allowed(url):
    domain = urlparse(url).netloc.lower().replace("www.", "")
    return any(d in domain for d in ALLOWED_DOMAINS)

def fetch_news():
    url = "https://api.gdeltproject.org/api/v2/doc/doc"

    params = {
        "query": KEYWORDS,
        "mode": "ArtList",
        "format": "json",
        "timespan": "24h",
        "maxrecords": 25,
        "sort": "HybridRel"
    }

    try:
        time.sleep(3)
        r = requests.get(url, params=params, timeout=30)

        if r.status_code == 429:
            print("GDELT rate limited: 429")
            return []

        if r.status_code != 200:
            print(f"GDELT error status: {r.status_code}")
            return []

        if not r.text.strip():
            print("GDELT returned empty response")
            return []

        try:
            data = r.json()
        except Exception as e:
            print("GDELT returned non-JSON response")
            print(str(e))
            return []

        articles = data.get("articles", [])
        results = []
        seen = set()

        for a in articles:
            title = a.get("title", "").strip()
            link = a.get("url", "").strip()
            domain = urlparse(link).netloc.lower().replace("www.", "")
            date = a.get("seendate", "")

            if not title or not link:
                continue

            if not domain_allowed(link):
                continue

            key = title.lower()[:90]
            if key in seen:
                continue

            seen.add(key)

            results.append({
                "title": title,
                "url": link,
                "domain": domain,
                "date": date
            })

        return results[:20]

    except Exception as e:
        print("fetch_news failed:")
        print(str(e))
        return []

def build_news_text(news):
    if not news:
        return """
过去24小时内，新闻接口未能从指定权威来源稳定抓取到足够新闻。

请在日报中明确说明：
“指定来源新闻不足，今日未能从 Reuters、Bloomberg、Financial Times、BBC、TechCrunch、36氪、虎嗅、AP News、Federal Reserve、White House、Treasury、Commerce、SEC、DOJ 等来源抓取到足够可核验新闻。”

不要编造新闻。
不要添加没有链接的新闻。
"""

    lines = []

    for i, n in enumerate(news, 1):
        lines.append(
            f"{i}. 标题：{n['title']}\n"
            f"来源域名：{n['domain']}\n"
            f"时间：{n['date']}\n"
            f"链接：{n['url']}\n"
        )

    return "\n".join(lines)

def generate_report(news_text):
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    prompt = f"""
你是一名严格遵守事实的美股信息整理员，不是投资顾问。

请根据以下过去24小时抓取到的新闻列表，生成中文《美股事实日报》。

重要规则：
1. 只基于我提供的新闻列表，不允许编造不存在的信息。
2. 不做预测，不判断明天涨跌。
3. 不给买入、卖出、持有建议。
4. 每条重要新闻必须附带原始链接。
5. 来源仅限以下类型：
Reuters、Bloomberg、Financial Times、BBC、TechCrunch、36氪、虎嗅、AP News、
Federal Reserve、White House、Treasury、Commerce、SEC、DOJ。
6. 重点关注影响美股的信息：
美联储、FOMC、鲍威尔、美联储官员讲话、美国政府官员发言、财政部、白宫、
CPI、PPI、非农、失业率、GDP、PMI、ISM、美债收益率、美元、油价、AI、半导体、
NVDA、TSLA、MSFT、META、AAPL、AMZN、AMD、GOOGL。
7. 全文必须超过1000个中文字符。
8. 如果新闻不足，请明确写“指定来源新闻不足”，不要编造。
9. 语言：中文。
10. 报告必须结构清晰，适合邮件阅读。

邮件结构：

【美股事实日报】
日期：{today}

一、今日重点摘要

二、美联储与美国政府动态

三、宏观经济与美债美元

四、AI、科技与半导体

五、重点公司新闻

六、地缘政治、监管与风险事件

七、原始新闻链接汇总

八、信息说明
说明：本邮件仅用于新闻事实整理，不构成投资建议。

以下是新闻列表：

{news_text}
"""

    response = model.generate_content(prompt)
    return response.text

def send_email(report):
    msg = MIMEText(report, "plain", "utf-8")
    msg["Subject"] = "美股事实日报"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

def main():
    news = fetch_news()
    news_text = build_news_text(news)
    report = generate_report(news_text)
    send_email(report)
    print("Daily factual market report sent successfully.")

if __name__ == "__main__":
    main()
