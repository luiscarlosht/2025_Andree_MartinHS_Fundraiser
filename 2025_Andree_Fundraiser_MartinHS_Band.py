#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import logging
from flask import Flask, request, abort
from twilio.twiml.messaging_response import MessagingResponse

# ----- Logging (works with systemd stdout or your log file) -----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ----- Config / Env -----
FUNDRAISER_URL = os.getenv("FUNDRAISER_URL", "https://vraise.org/sNQil1")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY")

# Models (override via env if desired)
PRIMARY_MODEL = os.getenv("OPENAI_PRIMARY_MODEL", "gpt-5")
FALLBACK_MODEL = os.getenv("OPENAI_FALLBACK_MODEL", "gpt-5-mini")

# ----- OpenAI client -----
from openai import OpenAI
from openai import APIError, RateLimitError, APITimeoutError

client = OpenAI(api_key=OPENAI_API_KEY)

# ----- Flask app -----
app = Flask(__name__)

@app.route("/health", methods=["GET"])
def health():
    return {"ok": True, "model_primary": PRIMARY_MODEL, "model_fallback": FALLBACK_MODEL}, 200

def ask_openai(prompt: str, max_retries: int = 2) -> str:
    """
    Try PRIMARY_MODEL first; on failure (quota, rate limit, transient), fall back to FALLBACK_MODEL.
    Returns plain text or raises an exception if both fail.
    """
    models_to_try = [PRIMARY_MODEL, FALLBACK_MODEL]
    last_err = None

    for model in models_to_try:
        for attempt in range(1, max_retries + 1):
            try:
                logging.info(f"[OpenAI] Using model={model}, attempt={attempt}")
                # OpenAI Responses API
                resp = client.responses.create(
                    model=model,
                    input=prompt,
                    temperature=0.6,
                )
                text = (resp.output_text or "").strip()
                if not text:
                    raise APIError("Empty response text")
                if model != PRIMARY_MODEL:
                    logging.warning(f"[OpenAI] FELL BACK to {model} and succeeded.")
                return text

            except (RateLimitError, APITimeoutError) as e:
                backoff = min(8.0, 1.5 ** attempt)
                logging.warning(f"[OpenAI] Transient error on {model}: {e}. Backing off {backoff:.1f}s")
                time.sleep(backoff)
                last_err = e
                continue

            except APIError as e:
                logging.error(f"[OpenAI] API error on {model}: {e}. Will try fallback if available.")
                last_err = e
                break

            except Exception as e:
                logging.exception(f"[OpenAI] Unexpected error on {model}: {e}")
                last_err = e
                break

    raise last_err or RuntimeError("OpenAI call failed without specific exception.")

def build_prompt(user_text: str) -> str:
    """
    Short, cost-efficient system+instruction prompt that’s bilingual and fundraising-focused.
    The model keeps answers concise and only includes the donation link when relevant.
    """
    return f"""You are a friendly, concise, bilingual (English/Spanish) fundraising assistant.
- Keep replies short (1–3 sentences).
- If the user asks how to donate or seems ready to help, include the donation link: {FUNDRAISER_URL}
- If they greet or ask general info, briefly explain it's for Andree Valentino (sophomore, French horn, Martin High School band) and funds support the band program.
- If they ask about small amounts, confirm $3–$5 is appreciated.
- If asked in Spanish, reply in Spanish; if asked in English, reply in English.
User: {user_text}
Assistant:"""

@app.route("/whatsapp", methods=["POST"])
def whatsapp_reply():
    # Twilio sends application/x-www-form-urlencoded
    form = request.form.to_dict()
    logging.info(f"[Webhook] Incoming WA form: {form}")

    # Basic validation: require Body
    incoming_msg = (form.get("Body") or "").strip()
    if not incoming_msg:
        # Still return a TwiML reply so Twilio isn't left hanging
        resp = MessagingResponse()
        resp.message("Hi! Please send a message to get started.")
        return str(resp)

    # Build prompt and ask OpenAI with fallback
    try:
        prompt = build_prompt(incoming_msg)
        answer = ask_openai(prompt)
    except Exception as e:
        logging.exception(f"[Bot] OpenAI failed on primary+fallback: {e}")
        answer = (
            "I’m having a brief technical hiccup. Please try again in a minute. "
            "Gracias por tu paciencia."
        )

    # Send TwiML response back to WhatsApp
    resp = MessagingResponse()
    resp.message(answer)
    return str(resp)

if __name__ == "__main__":
    # Bind to all interfaces so GCP/Nginx can reach it
    app.run(host="0.0.0.0", port=5000)
