"""Step 1 - scrape a prospect's website for raw signal."""
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
MAX_CHARS_PER_PAGE = 6000

# Pages most likely to carry compliance / stage / buyer signal.
KEY_PATHS = ["about", "security", "trust", "pricing", "customers", "careers", "compliance", "enterprise"]

# Third-party trust centres reveal an existing compliance vendor.
TRUST_VENDORS = ["vanta", "drata", "secureframe", "sprinto", "safebase", "whistic", "conveyor", "thoropass"]


def _clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text)[:MAX_CHARS_PER_PAGE]


def fetch_page(url: str) -> dict:
    """Fetch one URL. Returns {url, ok, text, links, html_hits}."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        r.raise_for_status()
    except requests.RequestException as e:
        return {"url": url, "ok": False, "text": f"(fetch failed: {e})", "links": [], "vendor_hits": []}
    soup = BeautifulSoup(r.text, "html.parser")
    links = sorted({urljoin(r.url, a["href"]).split("#")[0] for a in soup.find_all("a", href=True)})
    lower = r.text.lower()
    return {
        "url": r.url,
        "ok": True,
        "text": _clean_text(r.text),
        "links": links,
        "vendor_hits": [v for v in TRUST_VENDORS if v in lower],
    }


def scrape_site(domain: str) -> dict:
    """Homepage plus whichever key pages it links to."""
    home = fetch_page(f"https://{domain}")
    pages = [home]
    host = urlparse(home["url"]).netloc or domain
    seen = {home["url"]}
    for path in KEY_PATHS:
        match = next(
            (l for l in home["links"]
             if urlparse(l).netloc.endswith(domain.split("/")[0]) or urlparse(l).netloc == host
             if re.search(rf"/{path}\b", urlparse(l).path.lower())),
            None,
        )
        # trust.<domain> subdomains are common for trust centres
        if not match and path == "trust":
            match = next((l for l in home["links"] if urlparse(l).netloc.startswith("trust.")), None)
        if match and match not in seen:
            seen.add(match)
            pages.append(fetch_page(match))
    vendor_hits = sorted({v for p in pages for v in p["vendor_hits"]})
    return {
        "domain": domain,
        "pages": [{"url": p["url"], "ok": p["ok"], "text": p["text"]} for p in pages],
        "all_links": home["links"][:150],
        "trust_vendor_hits": vendor_hits,
    }
