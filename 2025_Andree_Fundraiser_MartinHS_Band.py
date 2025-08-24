#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import time
import logging
from datetime import datetime
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ---------- Config / Env ----------
FUNDRAISER_URL = os.getenv("FUNDRAISER_URL", "https://bit.ly/AndreeBand")
GOAL_USD = os.getenv("GOAL_USD", "1000")
DEADLINE = os.getenv("DEADLINE", "")            # e.g., "2025-09-30"
PRIMARY_MODEL = os.getenv("OPENAI_PRIMARY_MODEL", "gpt-5")
FALLBACK_MODEL = os.getenv("OPENAI_FALLBACK_MODEL", "gpt-5-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY")

# ---------- OpenAI client ----------
from openai import OpenAI
from openai import APIError, RateLimitError, APITimeoutError
client = OpenAI(api_key=OPENAI_API_KEY)

# ---------- Flask ----------
app = Flask(__name__)

@app.get("/health")
def health():
    return {
        "ok": True,
        "model_primary": PRIMARY_MODEL,
        "model_fallback": FALLBACK_MODEL,
        "fundraiser_url": FUNDRAISER_URL,
        "goal_usd": GOAL_USD,
        "deadline": DEADLINE,
    }, 200

# ---------- Helpers ----------
def is_spanish(text: str) -> bool:
    t = text.lower()
    spanish_markers = [
        "¿", "¡", "qué", "como", "cómo", "cuánto", "cuanto", "dónde", "para qué", "para que",
        "tarjeta", "mexicana", "donar", "donación", "pago", "ayudar", "compartir", "deducible"
    ]
    return any(w in t for w in spanish_markers)

def fmt_deadline():
    if not DEADLINE:
        return ""
    try:
        d = datetime.fromisoformat(DEADLINE)
        return d.strftime("%B %d, %Y")
    except Exception:
        return DEADLINE

DEADLINE_HUMAN = fmt_deadline()

def faq_router(user_text: str, sms: bool = False) -> str | None:
    """
    Return a canned answer if we recognize the intent.
    If sms=True, use ultra-short (<=160 char) variants.
    """
    txt = user_text.strip().lower()
    es = is_spanish(txt)

    # --- Patterns (EN & ES) ---
    p_money_for = [
        r"\bwhat\s+is\s+the\s+money\s+for\b", r"\bwhat\s+is\s+it\s+for\b", r"\bpurpose\b",
        r"\bpara\s+qué\s+es\s+el\s+dinero\b", r"\bpara\s+que\s+es\s+el\s+dinero\b", r"\bpara\s+qué\s+es\b",
    ]
    p_amount = [
        r"\bhow\s+much\s+should\s+i\s+donate\b", r"\bhow\s+much\b", r"\bamount\b", r"\bminimum\b",
        r"\bcu[aá]nto\s+(debo|puedo)\s+donar\b", r"\bmonto\b"
    ]
    p_mex_card = [
        r"\bmexican\s+card\b", r"\bmexico\s+card\b", r"\bworks\s+in\s+mexico\b",
        r"\btarjeta\s+mexicana\b", r"\bfunciona\s+en\s+m[eé]xico\b", r"\bacepta\s+tarjeta\b"
    ]
    p_about_andree = [
        r"\bwho\s+is\s+andree\b", r"\btell\s+me\s+about\s+andree\b",
        r"\bacerca\s+de\s+andree\b", r"\bqu[ié]n\s+es\s+andree\b"
    ]
    p_tax = [
        r"\btax\s+deductible\b", r"\btax\b", r"\breceipt\b",
        r"\bdeducible\b", r"\brecibo\b", r"\bfactura\b"
    ]
    p_deadline = [
        r"\bdeadline\b", r"\bwhen\s+does\s+it\s+end\b", r"\bby\s+when\b", r"\bgoal\b",
        r"\bmeta\b", r"\bfecha\s+l[ií]mite\b", r"\bcu[aá]ndo\s+termina\b"
    ]
    p_how_donate = [
        r"\bhow\s+do\s+i\s+donate\b", r"\bdonate\b", r"\bdonation\b", r"\blink\b",
        r"\bc[óo]mo\s+donar\b", r"\benlace\b", r"\bdonaci[oó]n\b"
    ]
    p_share = [
        r"\bcan\s+i\s+share\b", r"\bshare\b", r"\bpuedo\s+compartir\b", r"\bcompartir\b"
    ]
    p_thanks = [r"\bthanks\b", r"\bthank\s+you\b", r"\bgracias\b"]
    p_greeting = [r"\bhi\b", r"\bhello\b", r"\bhey\b", r"\bhol[ao]\b", r"\bbuenas\b"]

    def match_any(patterns):
        return any(re.search(p, txt) for p in patterns)

    # ---- SMS SHORT VARIANTS (<=160 chars) ----
    if sms:
        if match_any(p_money_for):
            return ("Funds help Martin HS band (instruments, uniforms, travel). Donate: "
                    f"{FUNDRAISER_URL}" if not es else
                    f"Fondo para la banda de Martin HS (instrumentos, uniformes, viajes). Dona: {FUNDRAISER_URL}")
        if match_any(p_amount):
            return (f"Every bit helps! Even $3–$5 adds up. Donate: {FUNDRAISER_URL}"
                    if not es else f"¡Todo ayuda! $3–$5 suma. Dona: {FUNDRAISER_URL}")
        if match_any(p_mex_card):
            return (f"Yes—most cards incl. Mexico work. Try: {FUNDRAISER_URL}"
                    if not es else f"Sí—funcionan tarjetas de México. Prueba: {FUNDRAISER_URL}")
        if match_any(p_about_andree):
            return (f"Andree is a Martin HS sophomore, French horn. Support: {FUNDRAISER_URL}"
                    if not es else f"Andree cursa 2º en Martin HS y toca corno. Apoya: {FUNDRAISER_URL}")
        if match_any(p_tax):
            return ("You’ll get an email receipt. Tax treatment varies; ask your tax advisor."
                    if not es else "Recibirás recibo por email. El tratamiento fiscal varía; consulta a tu asesor.")
        if match_any(p_deadline):
            if DEADLINE_HUMAN and GOAL_USD:
                return (f"Goal ${GOAL_USD}. Please donate by {DEADLINE_HUMAN}: {FUNDRAISER_URL}"
                        if not es else f"Meta ${GOAL_USD}. Dona antes del {DEADLINE_HUMAN}: {FUNDRAISER_URL}")
            return (f"Please donate when you can: {FUNDRAISER_URL}"
                    if not es else f"Dona cuando puedas: {FUNDRAISER_URL}")
        if match_any(p_how_donate):
            return (f"Tap to donate any amount: {FUNDRAISER_URL}"
                    if not es else f"Abre el enlace y dona: {FUNDRAISER_URL}")
        if match_any(p_share):
            return ("Yes, please share the link: " + FUNDRAISER_URL
                    if not es else "Sí, por favor comparte el enlace: " + FUNDRAISER_URL)
        if match_any(p_thanks):
            return ("Thank you! 🎺" if not es else "¡Gracias! 🎺")
        if match_any(p_greeting):
            return (f"Hi! Supporting Martin HS band. Donate: {FUNDRAISER_URL}"
                    if not es else f"¡Hola! Apoyamos la banda de Martin HS. Dona: {FUNDRAISER_URL}")
        return None

    # ---- WHATSAPP (richer text) ----
    if match_any(p_money_for):
        return (
            f"Funds support the Martin HS band (equipment, uniforms, travel, and program needs). "
            f"Andree is a sophomore who plays French horn. If you’d like to help: {FUNDRAISER_URL}"
            if not es else
            f"Los fondos apoyan a la banda de Martin HS (equipo, uniformes, viajes y necesidades del programa). "
            f"Andree cursa segundo año y toca corno francés. Si deseas ayudar: {FUNDRAISER_URL}"
        )
    if match_any(p_amount):
        return (
            f"Anything helps—small gifts like $3–$5 are perfect. Give what feels right. Donar: {FUNDRAISER_URL}"
            if not es else
            f"Todo ayuda—donativos de $3–$5 son perfectos. Aporta lo que te sea posible. Donar: {FUNDRAISER_URL}"
        )
    if match_any(p_mex_card):
        return (
            f"The page accepts major cards. If a Mexican card has trouble, try another card or the alternative option on the page. Test here: {FUNDRAISER_URL}"
            if not es else
            f"La página acepta tarjetas principales. Si una tarjeta mexicana falla, prueba otra o el método alterno de la página. Prueba aquí: {FUNDRAISER_URL}"
        )
    if match_any(p_about_andree):
        return (
            f"Andree Valentino is a sophomore at Martin High School and plays French horn in the band. "
            f"Your support goes straight to the band program: {FUNDRAISER_URL}"
            if not es else
            f"Andree Valentino cursa segundo año en Martin High School y toca corno francés en la banda. "
            f"Tu apoyo va directo al programa de banda: {FUNDRAISER_URL}"
        )
    if match_any(p_tax):
        return (
            "You’ll get an email receipt after donating. Tax treatment can vary; please consult your tax advisor."
            if not es else
            "Después de donar, recibirás un recibo por correo electrónico. El tratamiento fiscal puede variar; consulta a tu asesor."
        )
    if match_any(p_deadline):
        if DEADLINE_HUMAN and GOAL_USD:
            return (
                f"Our goal is ${GOAL_USD}. If possible, please donate by {DEADLINE_HUMAN}. Link: {FUNDRAISER_URL}"
                if not es else
                f"Nuestra meta es de ${GOAL_USD}. Si es posible, dona antes del {DEADLINE_HUMAN}. Enlace: {FUNDRAISER_URL}"
            )
        elif GOAL_USD:
            return (
                f"Our goal is ${GOAL_USD}. You can donate here: {FUNDRAISER_URL}"
                if not es else
                f"Nuestra meta es de ${GOAL_USD}. Puedes donar aquí: {FUNDRAISER_URL}"
            )
        else:
            return (
                f"You can donate anytime here: {FUNDRAISER_URL}"
                if not es else
                f"Puedes donar en cualquier momento aquí: {FUNDRAISER_URL}"
            )
    if match_any(p_how_donate):
        return (
            f"Thanks for helping! Tap this link, choose any amount, and submit: {FUNDRAISER_URL}"
            if not es else
            f"¡Gracias por apoyar! Abre este enlace, elige el monto que gustes y envía tu donación: {FUNDRAISER_URL}"
        )
    if match_any(p_share):
        share_en = f"Hi! I’m supporting Andree’s Martin HS band fundraiser. Chip in here: {FUNDRAISER_URL}"
        share_es = f"¡Hola! Apoyo la recaudación para la banda de Martin HS de Andree. Enlace: {FUNDRAISER_URL}"
        return (f"Yes, please share! You can copy this:\n\n{share_en}"
                if not es else f"¡Sí, por favor comparte! Puedes copiar esto:\n\n{share_es}")
    if match_any(p_thanks):
        return "You’re awesome—thank you! 🎺" if not es else "¡Muchas gracias! 🎺"
    if match_any(p_greeting):
        return (
            f"Hi! I’m helping Andree’s Martin HS band fundraiser. If you’d like to support, here’s the link: {FUNDRAISER_URL}"
            if not es else
            f"¡Hola! Estoy ayudando con la recaudación para la banda de Martin HS de Andree. Si quieres apoyar, aquí está el enlace: {FUNDRAISER_URL}"
        )

    return None

def ask_openai(prompt: str, max_retries: int = 2) -> str:
    """
    Try PRIMARY_MODEL first; on failure (quota, rate limit, transient), fall back to FALLBACK_MODEL.
    (No temperature param for Responses API.)
    """
    models_to_try = [PRIMARY_MODEL, FALLBACK_MODEL]
    last_err = None

    for model in models_to_try:
        for attempt in range(1, max_retries + 1):
            try:
                logging.info(f"[OpenAI] Using model={model}, attempt={attempt}")
                resp = client.responses.create(model=model, input=prompt)
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

def build_prompt(user_text: str, sms: bool) -> str:
    # Keep it brief for cost; allow the model to be concise. Slightly different instruction for SMS vs WhatsApp.
    style = "very short (1–2 sentences)" if sms else "short (1–3 sentences)"
    return f"""You are a friendly, concise, bilingual (English/Spanish) fundraising assistant.
- Keep replies {style}.
- If the user asks how to donate or is ready to help, include the donation link: {FUNDRAISER_URL}
- If they greet or ask general info, explain it's for Andree Valentino (sophomore, French horn, Martin High School band) and funds support the band program.
- Match the user's language: Spanish in Spanish, English in English.
User: {user_text}
Assistant:"""

# ---------- Webhooks ----------
@app.post("/whatsapp")
def whatsapp_reply():
    form = request.form.to_dict()
    logging.info(f"[Webhook] Incoming WA form: {form}")
    incoming_msg = (form.get("Body") or "").strip()
    resp = MessagingResponse()
    msg = resp.message()
    if not incoming_msg:
        msg.body("Hi! Please send a message to get started.")
        return str(resp)

    # WhatsApp richer answers
    canned = faq_router(incoming_msg, sms=False)
    if canned:
        msg.body(canned)
        return str(resp)

    try:
        prompt = build_prompt(incoming_msg, sms=False)
        answer = ask_openai(prompt)
        msg.body(answer)
    except Exception as e:
        logging.exception(f"[Bot] OpenAI failed (WA): {e}")
        msg.body("I’m having a brief technical hiccup. Please try again in a minute. Gracias por tu paciencia.")
    return str(resp)

@app.post("/sms")
def sms_reply():
    form = request.form.to_dict()
    logging.info(f"[Webhook] Incoming SMS form: {form}")
    incoming_msg = (form.get("Body") or "").strip()
    resp = MessagingResponse()
    msg = resp.message()
    if not incoming_msg:
        msg.body("Hi! Please send a message to get started. Reply STOP to unsubscribe.")
        return str(resp)

    # SMS short answers
    canned = faq_router(incoming_msg, sms=True)
    if canned:
        msg.body(canned)
        return str(resp)

    try:
        prompt = build_prompt(incoming_msg, sms=True)
        answer = ask_openai(prompt)
        # (Optional) ensure we keep answers concise for SMS:
        if len(answer) > 160:
            answer = answer[:157] + "..."
        msg.body(answer)
    except Exception as e:
        logging.exception(f"[Bot] OpenAI failed (SMS): {e}")
        msg.body("Temporary issue. Please try again soon. Reply STOP to unsubscribe.")
    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
