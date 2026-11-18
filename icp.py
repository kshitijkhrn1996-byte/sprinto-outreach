"""Sprinto's ICP - hard gates, then a fixed points table computed in Python.

The LLM never picks the score. It only reports, for each signal below, whether it is
present and the evidence (quote + URL). A signal with no evidence counts as absent.

Reasoning:
- Sprinto sells first-time compliance (SOC 2 / ISO 27001 / GDPR) to SaaS companies.
- The buying moment is when a company moves upmarket and enterprise buyers start demanding
  certifications, or when an audit is already under way.
- So a company qualifies when it has a reason to buy NOW (a primary trigger) AND a
  second, independent signal that confirms it - one signal alone is not enough, because
  almost every SaaS site has an "enterprise" page.
"""

# --- Hard gates: fail any one -> Not Qualified, regardless of points -------------------
GATES = {
    "is_b2b_saas": "Sells software to businesses on subscription. Agencies, marketplaces, consumer apps, hardware -> false.",
    "stage_in_range": "Roughly Series A-C / ~20-1000 employees. Check the news headlines for the latest funding round, acquisition or IPO. false ONLY with evidence of being pre-seed/seed-only, acquired by a large company, or public/large. Unknown -> true (flagged).",
    "not_sprinto_customer": "false if the site shows a Sprinto trust centre or names Sprinto as its compliance vendor.",
    "not_mature_programme": "false if they already hold BOTH SOC 2 Type II and ISO 27001 (or 4+ frameworks). Those are switch sales, not first-time buyers.",
}

# --- Points: primary triggers say "why now", supporting signals confirm it --------------
PRIMARY = {
    "enterprise_selling": (25, "Enterprise plan, SSO/SAML, 'contact sales', or named enterprise customers."),
    "compliance_in_motion": (25, "Audit in progress, a first certification in the last ~12 months (site or news), open security/GRC/compliance roles, or security questionnaires mentioned. Generic legal boilerplate (e.g. a privacy policy saying it complies with the IT Act) does NOT count."),
}
SUPPORTING = {
    "sensitive_data": (15, "Handles customer PII, financial, health, HR/employee, or security data."),
    "regulated_or_eu_buyers": (15, "Sells to finance, healthcare, government, or EU customers (GDPR)."),
}

# Threshold = smallest score that guarantees one primary trigger + one other signal.
#   One primary alone          = 25            -> fail (no corroboration)
#   Both supporting, no primary = 15 + 15 = 30 -> fail (no reason to buy now)
#   One primary + one supporting = 25 + 15 = 40 -> pass
# 40 is the lowest total that can only be reached with a primary trigger in it.
QUALIFY_THRESHOLD = PRIMARY["enterprise_selling"][0] + SUPPORTING["sensitive_data"][0]

ICP_RUBRIC = "SPRINTO ICP - assess each item; cite evidence (quote + URL) for anything you mark true.\n\nHARD GATES:\n" + \
    "\n".join(f"- {k}: {v}" for k, v in GATES.items()) + "\n\nSIGNALS:\n" + \
    "\n".join(f"- {k}: {d}" for k, (_, d) in {**PRIMARY, **SUPPORTING}.items())


def score(assessment: dict) -> dict:
    """Apply gates and the points table to the LLM's evidence-backed assessment."""
    gates = assessment.get("gates", {})
    signals = assessment.get("signals", {})

    failed_gates = [g for g in GATES if gates.get(g, {}).get("value") is False]

    def present(name):
        s = signals.get(name, {})
        return bool(s.get("present")) and bool((s.get("evidence") or "").strip())

    breakdown = {name: (pts if present(name) else 0) for name, (pts, _) in {**PRIMARY, **SUPPORTING}.items()}
    total = sum(breakdown.values())
    has_primary = any(breakdown[p] for p in PRIMARY)

    if failed_gates:
        decision, why = "Not Qualified", f"failed gate(s): {', '.join(failed_gates)}"
    elif total >= QUALIFY_THRESHOLD and has_primary:
        decision, why = "Qualified", f"{total} >= {QUALIFY_THRESHOLD} with a primary trigger"
    else:
        decision, why = "Not Qualified", f"{total} < {QUALIFY_THRESHOLD}" if total < QUALIFY_THRESHOLD else "no primary trigger"

    return {
        "decision": decision,
        "score": total,
        "threshold": QUALIFY_THRESHOLD,
        "points_breakdown": breakdown,
        "failed_gates": failed_gates,
        "stage_unverified": gates.get("stage_in_range", {}).get("unknown", False),
        "rule_applied": why,
    }
