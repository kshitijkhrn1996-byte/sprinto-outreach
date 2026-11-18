"""Step 3 - qualify against the ICP with a bounded agent loop.

Each iteration the LLM either submits its evidence-backed assessment, or asks to
fetch one more page from the company's site. After MAX_ITERATIONS fetches it is
forced to assess with what it has. The score and decision are computed in
icp.score() - the LLM never chooses them.
"""
import json

import config
from icp import GATES, ICP_RUBRIC, PRIMARY, SUPPORTING, score
from llm import ask_json
from steps.scrape import fetch_page

SYSTEM = f"""You assess prospects for Sprinto, a compliance automation platform.
You report facts with evidence; you do not decide or score.
{ICP_RUBRIC}"""

_gate_fmt = ",\n    ".join(f'"{g}": {{"value": true/false, "unknown": true/false, "evidence": "quote + URL"}}' for g in GATES)
_sig_fmt = ",\n    ".join(f'"{s}": {{"present": true/false, "evidence": "quote + URL, empty if absent"}}' for s in {**PRIMARY, **SUPPORTING})

ASSESS_KEYS = f"""{{
  "action": "assess",
  "gates": {{
    {_gate_fmt}
  }},
  "signals": {{
    {_sig_fmt}
  }},
  "trigger": "the single most likely reason they need compliance now",
  "reasoning": "2-4 sentences summarising the evidence"
}}"""

FETCH_KEYS = """{
  "action": "fetch",
  "url": "one URL from the available links list (or a same-domain URL like https://<domain>/security)",
  "missing_info": "which gate or signal you cannot assess yet and why"
}"""


def _news_block(news: dict | None) -> str:
    heads = (news or {}).get("headlines") or []
    if not heads:
        return "(no headlines found)"
    lines = "\n".join(f"- {h['date']} | {h['title']}" for h in heads)
    return f"""Headlines that mention "{news['name_searched']}". Some may be about a DIFFERENT company or thing
with the same name - use a headline only if it clearly matches this company's product/industry.
Cite a headline as evidence like: "<headline>" (Google News, <date>).
{lines}"""


def qualify(company: dict, scraped: dict, news: dict | None = None) -> dict:
    domain = scraped["domain"]
    links = scraped["all_links"]
    extra_context: list[dict] = []
    trace: list[dict] = []

    for iteration in range(1, config.MAX_ITERATIONS + 2):
        forced = iteration > config.MAX_ITERATIONS
        context = "\n\n".join(f"### Fetched {c['url']}\n{c['text']}" for c in extra_context) or "(none yet)"
        if forced:
            instruction = f"""You have reached the iteration limit ({config.MAX_ITERATIONS}).
You MUST assess now using only the information above. Reply with:
{ASSESS_KEYS}"""
        else:
            instruction = f"""If you can assess every gate and signal from the data, reply with:
{ASSESS_KEYS}
If a gate or signal cannot be assessed and one specific page would settle it, fetch ONE page instead. Reply with:
{FETCH_KEYS}
Iteration {iteration} of {config.MAX_ITERATIONS}. Do not fetch a URL already fetched."""

        prompt = f"""COMPANY: {domain}
TRUST-CENTRE VENDORS DETECTED IN HTML: {scraped['trust_vendor_hits'] or 'none'}
STRUCTURED DATA:
{json.dumps(company, indent=2)}

GOOGLE NEWS (5 searches: funding, acquisition/IPO, compliance, enterprise, general):
{_news_block(news)}

ADDITIONAL PAGES FETCHED:
{context}

AVAILABLE LINKS ON SITE:
{json.dumps(links[:120])}

{instruction}"""
        out = ask_json(prompt, system=SYSTEM)

        if out.get("action") == "fetch" and not forced:
            url = out.get("url", "")
            page = fetch_page(url)
            extra_context.append({"url": page["url"], "text": page["text"][:4000]})
            trace.append({"iteration": iteration, "action": "fetch", "url": url,
                          "missing_info": out.get("missing_info"), "ok": page["ok"]})
            continue

        trace.append({"iteration": iteration, "action": "assess", "forced": forced})
        result = score(out)
        result.update({
            "gates": out.get("gates", {}),
            "signals": out.get("signals", {}),
            "signals_found": [f"{k}: {v.get('evidence')}" for k, v in out.get("signals", {}).items() if v.get("present")],
            "trigger": out.get("trigger"),
            "reasoning": out.get("reasoning"),
            "agent_trace": trace,
            "iterations_used": len([t for t in trace if t["action"] == "fetch"]),
        })
        return result
