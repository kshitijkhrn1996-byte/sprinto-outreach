import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
HUNTER_API_KEY = os.environ["HUNTER_API_KEY"]

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# Per the brief, every email lands in my own inbox for review - never the prospect.
# Set in .env (kept out of the public repo).
TO_EMAIL = os.environ["TO_EMAIL"]

# Agent loop guard for Step 3.
MAX_ITERATIONS = 3

SENDER_NAME = os.getenv("SENDER_NAME", "Kshitij")
SENDER_TITLE = os.getenv("SENDER_TITLE", "Growth, Sprinto")
