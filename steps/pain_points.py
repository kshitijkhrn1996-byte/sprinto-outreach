"""Step 5 - the two most likely pain points for this PoC."""
import json

from llm import ask_json


def pain_points(company: dict, qualification: dict, poc: dict) -> dict:
    prompt = f"""You are a B2B sales researcher for Sprinto (automates SOC 2, ISO 27001, GDPR audits:
continuous control monitoring, evidence collection, policy templates, auditor network, trust centre).

Identify the TWO most likely compliance-related pain points for this specific person,
given their role and the company's situation. Ground each one in a concrete signal from the data -
no generic pains that could apply to anyone.

PERSON: {poc['name']} - {poc.get('position')} ({poc.get('seniority')}, {poc.get('department')})
COMPANY DATA: {json.dumps(company, indent=2)}
QUALIFICATION: trigger = {qualification.get('trigger')}; signals = {qualification.get('signals_found')}

Reply JSON:
{{"pain_points": [
   {{"pain": "short statement in their words", "evidence": "the signal it is based on",
     "why_this_role": "why this person feels it", "sprinto_angle": "how Sprinto relieves it"}},
   {{...}}
 ]}}"""
    return ask_json(prompt)
