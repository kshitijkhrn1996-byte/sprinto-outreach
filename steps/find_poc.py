"""Step 4 - find the right point of contact via Hunter.io Domain Search."""
import json

import requests

import config
from llm import ask_json

HUNTER_URL = "https://api.hunter.io/v2/domain-search"

# Who owns "get us compliant" at a Series A-C SaaS company, best first.
# Under ~50 people the founder/CTO owns it; larger, a security or compliance lead does.
TARGET_PERSONAS = """Preferred buyer, in order:
1. Head of Security / CISO / Security & Compliance lead / GRC manager (owns the audit)
2. CTO / VP Engineering (owns it when there is no security hire)
3. CEO / Co-founder (owns it at small companies, or when deals are blocked on compliance)
4. COO / VP Operations, or VP Sales / CRO (feels the enterprise-deal pressure)
Avoid: interns, recruiters, marketing, support, generic inboxes."""


def hunter_search(domain: str) -> list[dict]:
    params = {"domain": domain, "api_key": config.HUNTER_API_KEY, "limit": 10, "type": "personal"}
    r = requests.get(HUNTER_URL, params=params, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"Hunter error {r.status_code}: {r.text[:300]}")
    emails = r.json().get("data", {}).get("emails", [])
    return [
        {
            "name": f"{e.get('first_name') or ''} {e.get('last_name') or ''}".strip(),
            "first_name": e.get("first_name"),
            "email": e.get("value"),
            "position": e.get("position"),
            "seniority": e.get("seniority"),
            "department": e.get("department"),
            "confidence": e.get("confidence"),
            "linkedin": e.get("linkedin"),
        }
        for e in emails
    ]


def find_poc(domain: str, company: dict, qualification: dict) -> dict:
    candidates = [c for c in hunter_search(domain) if c["first_name"]]
    if not candidates:
        return {"found": False, "reason": "Hunter returned no named contacts for this domain", "candidates": []}

    prompt = f"""Pick the single best person to receive a cold email from Sprinto (compliance automation).
{TARGET_PERSONAS}

Company: {company.get('company_name')} - {company.get('one_liner')}
Estimated employees: {company.get('estimated_employees')}
Why they qualified: {qualification.get('trigger')}

Candidates from Hunter.io:
{json.dumps(candidates, indent=2)}

Reply JSON: {{"index": <0-based index into candidates>, "reasoning": "why this person, 1-2 sentences"}}"""
    pick = ask_json(prompt)
    idx = pick.get("index", 0)
    if not isinstance(idx, int) or not 0 <= idx < len(candidates):
        idx = 0
    return {"found": True, "poc": candidates[idx], "reasoning": pick.get("reasoning"), "candidates": candidates}
