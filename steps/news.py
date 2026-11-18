"""Step 2b - recent Google News headlines (plain Python, no LLM).

Exactly 5 searches per company via the free Google News RSS feed. Headlines
are passed into the qualify step's existing prompt, so this adds no LLM calls.
"""
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote

import requests

RSS = "https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
PER_QUERY = 3      # top results kept from each search
MAX_HEADLINES = 15

# What each search is for - stage, exits, compliance, upmarket, general context.
QUERIES = [
    ("funding", '"{name}" funding OR raises OR "Series A" OR "Series B" OR "Series C"'),
    ("exit", '"{name}" acquired OR acquisition OR IPO OR listing'),
    ("compliance", '"{name}" "SOC 2" OR "ISO 27001" OR GDPR OR compliance OR audit'),
    ("enterprise", '"{name}" enterprise OR customers OR partnership OR expands'),
    ("general", '"{name}" {industry}'),
]


def search_news(name: str, industry: str = "") -> dict:
    headlines, seen, searches = [], set(), []
    # Case-sensitive: "Plane" the company, not "control plane" or "plane crash".
    word = re.compile(rf"\b{re.escape(name)}\b")
    for topic, template in QUERIES:
        q = template.format(name=name, industry=industry or "").strip()
        try:
            r = requests.get(RSS.format(q=quote(q)), timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            items = ET.fromstring(r.content).findall("./channel/item")
        except (requests.RequestException, ET.ParseError) as e:
            searches.append({"topic": topic, "query": q, "kept": 0, "error": str(e)})
            continue
        kept = 0
        for it in items:
            title = it.findtext("title") or ""
            # Drop results that don't actually name the company.
            if kept >= PER_QUERY or not word.search(title) or title in seen:
                continue
            seen.add(title)
            kept += 1
            headlines.append({
                "topic": topic,
                "date": (it.findtext("pubDate") or "")[5:16],
                "title": title,
                "url": it.findtext("link"),
            })
        searches.append({"topic": topic, "query": q, "kept": kept})
    return {"name_searched": name, "searches": searches, "headlines": headlines[:MAX_HEADLINES]}
