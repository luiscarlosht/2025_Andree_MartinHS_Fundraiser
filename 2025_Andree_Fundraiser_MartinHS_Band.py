import os
import time
import logging
from openai import OpenAI
from openai import APIError, RateLimitError, APITimeoutError

# Ensure logging goes to your systemd log file
logging.basicConfig(level=logging.INFO)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

PRIMARY_MODEL = os.getenv("OPENAI_PRIMARY_MODEL", "gpt-5")
FALLBACK_MODEL = os.getenv("OPENAI_FALLBACK_MODEL", "gpt-5-mini")

def ask_openai(prompt: str, max_retries: int = 2) -> str:
    """
    Try PRIMARY_MODEL, then FALLBACK_MODEL on failure.
    Uses lightweight retries for transient errors.
    Returns plain text. Raises last exception if everything fails.
    """
    models_to_try = [PRIMARY_MODEL, FALLBACK_MODEL]
    last_err = None

    for model in models_to_try:
        for attempt in range(1, max_retries + 1):
            try:
                logging.info(f"[OpenAI] Using model={model}, attempt={attempt}")
                resp = client.responses.create(
                    model=model,
                    input=prompt,
                    temperature=0.7,
                )
                text = resp.output_text.strip()
                if not text:
                    raise APIError("Empty response text")
                if model != PRIMARY_MODEL:
                    logging.warning(f"[OpenAI] FELL BACK to {model} and succeeded.")
                return text

            except (RateLimitError, APITimeoutError) as e:
                # transient — brief backoff then retry (or switch models)
                backoff = 1.5 ** attempt
                logging.warning(f"[OpenAI] Transient error on {model}: {e}. Backing off {backoff:.1f}s")
                time.sleep(backoff)
                last_err = e
                continue

            except APIError as e:
                # hard API error (includes insufficient_quota)
                logging.error(f"[OpenAI] API error on {model}: {e}. Will try fallback if available.")
                last_err = e
                break  # break retry loop and move to next model

            except Exception as e:
                # catch-all to avoid crashing webhook
                logging.exception(f"[OpenAI] Unexpected error on {model}: {e}")
                last_err = e
                break

    # If we got here, both models failed
    raise last_err or RuntimeError("OpenAI call failed without specific exception.")
