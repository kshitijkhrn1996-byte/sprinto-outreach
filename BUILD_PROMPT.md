# Build prompt: Sprinto cold outreach engine

Paste everything below the line into Claude Code (or another coding agent).

---

Build an automated cold outreach pipeline in Python for **Sprinto**, a company that automates compliance certifications (SOC 2, ISO 27001, GDPR) for SaaS companies. Today their Growth Lead does outbound by hand. Each company takes 15–20 minutes: research it, find who to contact, and write a personal first email. They do 8–15 companies a week, and quality drops toward the end of the list.

The system takes a list of company domains and runs end to end without a human making decisions at each step. Every decision it makes must be explainable: why this company qualified, why this person, why the email says what it says.

## Stack
- Python 3.12: `requests`, `beautifulsoup4`, `google-genai`, `python-dotenv`, `flask`
- LLM: Google Gemini (model name set in `.env`, default `gemini-3.5-flash`). Every LLM call returns JSON (`response_mime_type="application/json"`) and retries 3 times.
- Contacts: Hunter.io Domain Search API (free tier: 25 searches/month)
- Sending: Gmail SMTP using an app password
- `.env.example` with: `GEMINI_API_KEY`, `GEMINI_MODEL`, `HUNTER_API_KEY`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `SENDER_NAME`, `SENDER_TITLE`. Add `.env` and `runs/` to `.gitignore`.

## Project layout
```
config.py        env vars; TO_EMAIL hardcoded; MAX_ITERATIONS = 3
llm.py           ask_json(prompt, system) -> dict
icp.py           the fit rules + score() (see below)
steps/scrape.py, extract.py, qualify.py, find_poc.py, pain_points.py, draft_email.py, send_email.py
pipeline.py      CLI: python pipeline.py domains.txt [--dry-run]
app.py + templates/index.html   local dashboard on port 5190
runs/            one JSON decision log per company per run
```

## The 7 steps

**1. Scrape** (`scrape.py`): fetch `https://<domain>` plus any same-site links whose path contains about, security, trust, pricing, customers, careers, compliance or enterprise. Also follow `trust.<domain>` subdomains. Strip scripts and styles, and keep about 6,000 characters per page. Scan the raw HTML for compliance-tool names (sprinto, vanta, drata, secureframe, safebase, whistic, conveyor, thoropass) and return them as `trust_vendor_hits`. Expose `fetch_page(url)` so step 3 can reuse it.

**2. Extract** (`extract.py`): the LLM turns the page text into JSON with these fields:
- what they sell; is_saas; is_b2b; target customers
- sells_to_enterprise; industry; handles_sensitive_data
- estimated_stage; estimated_employees; funding mentions
- compliance_status: frameworks claimed, audits in progress, has_trust_page, trust_vendor
- enterprise-pressure signals; hiring signals; recent news

Use null or "unknown" where the text doesn't say. No guessing.

**2b. Google News** (`news.py`, plain Python, no LLM call): run exactly **5 searches** on the free Google News RSS feed (`news.google.com/rss/search?q=...&hl=en-IN&gl=IN&ceid=IN:en`). Each one is `"<company name>"` plus a topic:
- funding / Series A–C
- acquired / IPO
- SOC 2 / ISO 27001 / GDPR / compliance / audit
- enterprise / customers / partnership
- the company's industry

Keep the top 3 results per search, and only titles that contain the company name as a **case-sensitive** whole word ("Plane" the company, not "control plane"). Dedupe, cap at 15 headlines (date + title + link), and store them in the run log. Pass them into step 3's prompt (about 400 tokens) with an instruction to ignore headlines about a different company with the same name.

**3. Qualify** (`qualify.py` + `icp.py`). **The LLM reports evidence; code makes the decision.**
- The LLM gets the rubric, the extracted facts, the HTML vendor hits and the site's link list. Each round it replies with one of two actions:
  - `{"action":"fetch","url":...,"missing_info":...}` to read one more page, or
  - `{"action":"assess","gates":{...},"signals":{...},"trigger":...,"reasoning":...}` to submit its assessment.
- **Agent loop:** allow at most `MAX_ITERATIONS = 3` fetches. After that, the prompt forces an assessment using whatever context exists. Record every round in `agent_trace`.
- Every gate and signal comes back as value/present + `evidence` (a quote + URL).
- `icp.score()` then applies these rules in Python:

**Hard gates.** A gate fails only on an explicit `false`; "unknown" passes but is flagged.
| Gate | Rule |
|---|---|
| is_b2b_saas | Sells software to businesses on subscription. Agencies, marketplaces, consumer apps and hardware fail. |
| stage_in_range | Roughly Series A–C / 20–1000 employees. Check the news for the latest round, acquisition or IPO. Fails only with evidence of being seed-only, acquired, or public/large. |
| not_sprinto_customer | Fails if there's a Sprinto trust centre or Sprinto is named as their vendor. |
| not_mature_programme | Fails if they already hold BOTH SOC 2 Type II and ISO 27001, or 4+ frameworks. That would be a switch sale, not a first-time buyer. |

**Points.** A signal counts only if it has non-empty evidence.
| Signal | Type | Points |
|---|---|---|
| enterprise_selling: enterprise plan, SSO/SAML, "contact sales", enterprise logos | primary ("why now") | 25 |
| compliance_in_motion: audit in progress, first certification in the last ~12 months (site or news), security/GRC hiring, security questionnaires. Legal boilerplate doesn't count. | primary ("why now") | 25 |
| sensitive_data: PII, financial, health, HR or security data | supporting | 15 |
| regulated_or_eu_buyers: finance, healthcare, government or EU/GDPR customers | supporting | 15 |

**Decision:** Qualified = no gate failed AND score ≥ 40 AND at least one primary signal present.
- **Why 40:** it's one primary (25) plus one supporting (15).
- A primary alone (25) or both supporting signals (30) can't reach it.
- So every qualified company has a reason to buy now plus a second, independent signal confirming it.
- Compute the threshold in code from the point values. Don't hardcode 40 as a magic number.

Return: decision, score, threshold, points_breakdown, failed_gates, stage_unverified, rule_applied, gates, signals, trigger, reasoning, agent_trace, iterations_used.

**4. Find the contact** (`find_poc.py`): call Hunter `domain-search` (type=personal, limit=10) **only for qualified companies**, to save credits. The LLM picks one candidate, by index, using this priority order:
1. Head of Security / CISO / GRC
2. CTO / VP Engineering
3. CEO / co-founder
4. COO / VP Sales

Avoid interns, recruiters, marketing, support and generic inboxes. Return the pick, a 1–2 sentence reason, and all candidates.

**5. Pain points** (`pain_points.py`): the two most likely compliance pain points for this specific person. Each one has: pain, evidence (a concrete signal from the data), why_this_role, and sprinto_angle. No generic pains.

**6. Write the email** (`draft_email.py`). The rules:
- First name only; under 120 words; plain text.
- Open with a specific hook about THEIR company. Never "hope this finds you well" or "came across your website".
- One pain point, one sentence on how Sprinto helps with a concrete outcome, and one low-friction ask.
- No links or attachments.
- Subject under 7 words, specific, not salesy.

Return: subject, body, hook, hook_source, pain_point_used.

**7. Send** (`send_email.py`): Gmail SMTP_SSL on port 465. **Hardcode `To:` to my own email** (`<your email>`), never the prospect. At the bottom, append a "[Review copy] Intended for: name <email>, title at company" note.

## Pipeline + logs
- `run_domain(domain, dry_run, log=...)` runs the steps in order. It stops early with a clear status:
  - `skipped: site unreachable`
  - `not qualified`
  - `skipped: no contact found`
  - `drafted (dry run)`
  - `sent`
  - `error: …`
- Write each company's full record (pages scraped, facts, qualification, PoC, pain points, email, status) to `runs/<timestamp>_<domain>.json`.

## Dashboard (`app.py`, Flask, port 5190)

API:
- `GET /api/meta`
- `GET /api/runs`: latest run per domain
- `POST /api/run {domains, auto_send}`: runs in a background thread, returns a job_id
- `GET /api/job/<id>`: live per-domain progress
- `POST /api/send/<file>`: sends a stored draft

Single page, plain HTML/CSS/JS, light and dark mode. It's written to be presented, so use plain-English labels everywhere. Three sections, linked from a sticky top bar:

1. **How it works**
   - The 7 steps as cards: name, one-line description, tool used.
   - The fit test in three parts:
     - **Checks:** the gates written as questions, e.g. "Is it already a Sprinto customer? needs No".
     - **Score:** the signals as questions, tagged "why now" or "supporting", with their points.
     - **Decide:** why 40, with worked examples: 25 → no, 30 → no, 40 → yes.
2. **Results**
   - A run box (domains textarea, "also send the emails" toggle) with live progress per domain (a 7-segment bar plus the current step in words).
   - A funnel in words: N checked → fit Sprinto → have a contact → emails written → sent, each with "x of y".
   - A table: company, Fit?, a score bar coloured by signal with a threshold marker, "What happened" in plain words (e.g. "Out: already fully certified", "Fits, but no contact found"), and the contact.
3. **Walkthrough** for the selected company
   - A one-sentence verdict generated from the data, e.g. "Plane is not a fit because it is already fully certified. Evidence: …"
   - Then the 7 steps as a vertical timeline. Each step asks a question and gives a plain answer plus details:
     - What did we read?
     - What did we learn? (fact grid)
     - Do they fit? (checks with Yes/No + evidence; points with evidence; the pages the agent fetched and why)
     - Who should get the email? (pick, why, all Hunter candidates)
     - What problems do they likely have?
     - What do we say? (email in a mail-client layout + "why it's written this way")
     - Was it sent? (send button)
   - Mark the step where a company stopped with a red ✕; grey out the steps after it.

## Done means
- `python pipeline.py domains.txt --dry-run` runs a mixed list end to end. Some companies get rejected, each with quoted evidence, and at least one qualifies with a named contact and a drafted email.
- With Gmail credentials set, a personalised email lands in my inbox, addressed to a real person by first name, with a hook a human would actually reply to.
- For any company I can explain from the dashboard why it qualified or didn't, why that person was picked, and why the email was written that way.
