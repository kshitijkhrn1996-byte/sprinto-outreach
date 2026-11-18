"""Dashboard for the outreach pipeline.

    python app.py   ->  http://localhost:5190

Also runs on Vercel (api/index.py). There the bundled runs/ folder is read-only
seed data, new runs are written to /tmp, and the browser keeps its own runs.
"""
import json
import os
import re
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request

import config
from icp import GATES, PRIMARY, QUALIFY_THRESHOLD, SUPPORTING
from pipeline import RUNS_DIR, run_domain
from steps.send_email import send_email

app = Flask(__name__)
ON_VERCEL = bool(os.getenv("VERCEL"))
WRITE_DIR = Path("/tmp/runs") if ON_VERCEL else RUNS_DIR
READ_DIRS = [RUNS_DIR, WRITE_DIR] if ON_VERCEL else [RUNS_DIR]


def _mask(email: str | None) -> str | None:
    """s****@entrar.in - the site is public and these are real people."""
    if not email or "@" not in email:
        return email
    user, domain = email.split("@", 1)
    return f"{user[0]}{'*' * 4}@{domain}"


def _public(rec: dict) -> dict:
    rec = json.loads(json.dumps(rec))
    poc = rec.get("poc") or {}
    if poc.get("poc"):
        poc["poc"]["email"] = _mask(poc["poc"].get("email"))
    for c in poc.get("candidates", []):
        c["email"] = _mask(c.get("email"))
    return rec


def _find(name: str) -> Path | None:
    if not re.fullmatch(r"[\w.\-]+\.json", name):
        return None
    for d in READ_DIRS:
        if (d / name).is_file():
            return d / name
    return None


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/meta")
def meta():
    return jsonify({
        "to_email": _mask(config.TO_EMAIL),
        "max_iterations": config.MAX_ITERATIONS,
        "threshold": QUALIFY_THRESHOLD,
        "gates": GATES,
        "signals": {k: {"points": p, "desc": d, "kind": "primary"} for k, (p, d) in PRIMARY.items()}
                   | {k: {"points": p, "desc": d, "kind": "supporting"} for k, (p, d) in SUPPORTING.items()},
        "gmail_configured": bool(config.GMAIL_ADDRESS and config.GMAIL_APP_PASSWORD),
    })


@app.get("/api/runs")
def runs():
    out = []
    for d in READ_DIRS:
        for f in d.glob("*.json") if d.is_dir() else []:
            rec = json.loads(f.read_text())
            rec["_file"] = f.name
            out.append(_public(rec))
    out.sort(key=lambda r: r["_file"], reverse=True)
    return jsonify(out)


@app.post("/api/run-one")
def run_one():
    """Run all 7 steps for one domain and return the record (the page loops over domains)."""
    body = request.get_json(force=True)
    domain = (body.get("domain") or "").strip().replace("https://", "").replace("http://", "").strip("/")
    if not domain:
        return jsonify({"error": "no domain"}), 400
    rec = run_domain(domain, dry_run=not body.get("auto_send"), log=lambda *_: None)
    name = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{domain}.json"
    rec["_file"] = name
    WRITE_DIR.mkdir(parents=True, exist_ok=True)
    (WRITE_DIR / name).write_text(json.dumps(rec, indent=2))
    return jsonify(_public(rec))


@app.post("/api/send/<name>")
def send(name):
    path = _find(name)
    if not path:
        return jsonify({"error": "This run is no longer on the server - run the company again."}), 404
    rec = json.loads(path.read_text())
    if "email" not in rec:
        return jsonify({"error": "no drafted email in this run"}), 400
    try:
        rec["send"] = send_email(rec["email"], rec["poc"]["poc"], rec["company"])
        rec["status"] = "sent"
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    if path.parent == WRITE_DIR:
        path.write_text(json.dumps(rec, indent=2))
    rec["_file"] = name
    return jsonify(_public(rec))


if __name__ == "__main__":
    RUNS_DIR.mkdir(exist_ok=True)
    app.run(port=5190, debug=False)
