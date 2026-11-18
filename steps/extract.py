"""Step 2 - turn raw website text into structured company data."""
import json

from llm import ask_json

SCHEMA = {
    "company_name": "string",
    "one_liner": "what they sell, one sentence",
    "is_saas": "bool",
    "is_b2b": "bool",
    "target_customers": "who buys (SMB / mid-market / enterprise / regulated industries)",
    "sells_to_enterprise": "bool or null if unknown",
    "industry": "e.g. fintech, HR tech, devtools, healthtech",
    "handles_sensitive_data": "bool or null - customer PII, financial, health, employee data",
    "estimated_stage": "pre-seed / seed / Series A / Series B / Series C / later / public / unknown",
    "estimated_employees": "integer or null",
    "funding_mentions": "any funding round / investor mentions verbatim, or null",
    "compliance_status": {
        "frameworks_claimed": "list e.g. SOC 2 Type II, ISO 27001, GDPR, HIPAA",
        "in_progress_mentions": "verbatim mentions of audits in progress, or null",
        "has_trust_page": "bool",
        "trust_vendor": "vanta/drata/secureframe/... if detected, else null",
    },
    "enterprise_pressure_signals": "list of concrete signals: enterprise plan, SSO/SAML, security questionnaire mentions, big-logo customers",
    "hiring_signals": "list of relevant open roles (security, compliance, GRC, enterprise sales)",
    "notable_recent_news": "launches, funding, expansion - verbatim-ish, or null",
}


def extract(scraped: dict) -> dict:
    pages = "\n\n".join(f"### {p['url']}\n{p['text']}" for p in scraped["pages"] if p["ok"])
    prompt = f"""Extract structured data about the company at {scraped['domain']} from its website text.
Only use what the text supports; use null for unknowns. Do not guess funding stage from nothing -
infer it only from concrete hints (team size, funding mentions, customer logos) and say "unknown" otherwise.

Trust-centre vendors detected in page HTML: {scraped['trust_vendor_hits'] or 'none'}

Return JSON with exactly these keys:
{json.dumps(SCHEMA, indent=2)}

WEBSITE TEXT:
{pages}"""
    return ask_json(prompt)
