"""Step 6 - draft a personalised cold email with a specific hook."""
import json

import config
from llm import ask_json

STYLE = """Rules for the email:
- Address them by first name. Under 120 words in the body. Plain text, no bullet lists, no emojis.
- Open with a specific hook taken from THEIR company (a launch, an enterprise plan, a hiring post,
  a trust page, a customer logo) - never "I hope this finds you well" or "I came across your website".
- Connect the hook to ONE pain point in a sentence, then one sentence on how Sprinto helps,
  with a concrete outcome (e.g. SOC 2 audit-ready in weeks, not months; questionnaires answered from a trust centre).
- One low-friction ask (a 15-minute call or "worth a look?"). No attachments, no links.
- Subject line: under 7 words, lowercase-ish, specific to them, not salesy.
- Sound like a person, not a marketing team."""


def draft_email(company: dict, qualification: dict, poc: dict, pains: dict) -> dict:
    prompt = f"""Write a cold email from {config.SENDER_NAME} ({config.SENDER_TITLE}) to {poc['name']},
{poc.get('position')} at {company.get('company_name')}.

{STYLE}

COMPANY: {json.dumps(company, indent=2)}
WHY THEY QUALIFIED: {qualification.get('reasoning')}
PAIN POINTS: {json.dumps(pains.get('pain_points'), indent=2)}

Reply JSON:
{{"subject": "...", "body": "full email body including greeting and sign-off",
  "hook": "the specific fact the opener uses", "hook_source": "where that fact came from",
  "pain_point_used": "which pain point and why it was chosen over the other"}}"""
    return ask_json(prompt)
