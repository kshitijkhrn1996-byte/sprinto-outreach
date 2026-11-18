import json
import time

from google import genai
from google.genai import types

import config

_client = genai.Client(api_key=config.GEMINI_API_KEY)


def ask_json(prompt: str, system: str = "", retries: int = 3) -> dict:
    """Call Gemini and parse a JSON object from the reply."""
    cfg = types.GenerateContentConfig(
        system_instruction=system or None,
        response_mime_type="application/json",
        temperature=0.3,
    )
    last_err = None
    for attempt in range(retries):
        try:
            resp = _client.models.generate_content(
                model=config.GEMINI_MODEL, contents=prompt, config=cfg
            )
            return json.loads(resp.text)
        except Exception as e:  # rate limits / malformed JSON
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"LLM call failed: {last_err}")
