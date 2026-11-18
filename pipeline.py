"""Sprinto cold outreach pipeline.

Usage:
    python pipeline.py domains.txt            # full run, sends emails
    python pipeline.py domains.txt --dry-run  # everything except sending
    python pipeline.py acme.com rippling.com  # domains inline
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from steps.draft_email import draft_email
from steps.extract import extract
from steps.find_poc import find_poc
from steps.news import search_news
from steps.pain_points import pain_points
from steps.qualify import qualify
from steps.scrape import scrape_site
from steps.send_email import send_email

RUNS_DIR = Path(__file__).parent / "runs"


def log(domain: str, msg: str) -> None:
    print(f"[{domain}] {msg}", flush=True)


def run_domain(domain: str, dry_run: bool, log=log) -> dict:
    record = {"domain": domain, "started_at": datetime.now().isoformat(timespec="seconds")}
    try:
        log(domain, "1/7 scraping")
        scraped = scrape_site(domain)
        record["pages_scraped"] = [p["url"] for p in scraped["pages"]]
        if not any(p["ok"] for p in scraped["pages"]):
            record["status"] = "skipped: site unreachable"
            return record

        log(domain, "2/7 extracting")
        company = extract(scraped)
        record["company"] = company

        log(domain, "2/7 checking Google News")
        name = company.get("company_name") or domain.split(".")[0].capitalize()
        news = search_news(name, company.get("industry") or "")
        record["news"] = news

        log(domain, "3/7 qualifying")
        q = qualify(company, scraped, news)
        record["qualification"] = q
        log(domain, f"    -> {q['decision']} (score {q.get('score')}, {q['iterations_used']} extra fetches)")
        if q["decision"] != "Qualified":
            record["status"] = "not qualified"
            return record

        log(domain, "4/7 finding PoC (Hunter.io)")
        poc_result = find_poc(domain, company, q)
        record["poc"] = poc_result
        if not poc_result["found"]:
            record["status"] = "skipped: no contact found"
            return record
        poc = poc_result["poc"]
        log(domain, f"    -> {poc['name']}, {poc.get('position')}")

        log(domain, "5/7 pain points")
        pains = pain_points(company, q, poc)
        record["pain_points"] = pains

        log(domain, "6/7 drafting email")
        draft = draft_email(company, q, poc, pains)
        record["email"] = draft

        if dry_run:
            log(domain, "7/7 dry run - not sending")
            record["status"] = "drafted (dry run)"
        else:
            log(domain, "7/7 sending via Gmail")
            record["send"] = send_email(draft, poc, company)
            record["status"] = "sent"
    except Exception as e:
        record["status"] = f"error: {e}"
        log(domain, f"ERROR {e}")
    return record


def main(argv: list[str]) -> None:
    dry_run = "--dry-run" in argv
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    if len(args) == 1 and Path(args[0]).is_file():
        domains = [l.strip() for l in Path(args[0]).read_text().splitlines() if l.strip() and not l.startswith("#")]
    else:
        domains = args
    domains = [d.replace("https://", "").replace("http://", "").strip("/") for d in domains]

    RUNS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    results = []
    for domain in domains:
        rec = run_domain(domain, dry_run)
        results.append(rec)
        (RUNS_DIR / f"{stamp}_{domain}.json").write_text(json.dumps(rec, indent=2))

    print("\nSUMMARY")
    for r in results:
        print(f"  {r['domain']:<28} {r['status']}")
    print(f"\nFull decision logs: {RUNS_DIR}")


if __name__ == "__main__":
    main(sys.argv[1:])
