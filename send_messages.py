#!/usr/bin/env python3
import argparse, csv, json, os, sys, time, datetime
from pathlib import Path
from twilio.rest import Client

# ============================ CONFIG (ENV / DEFAULTS) ============================

STATUS_CALLBACK_URL = os.getenv("STATUS_CALLBACK_URL", "")

DEFAULT_SMS_FROM = os.getenv("TWILIO_SMS_FROM", "")
WA_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "")

# Twilio Content Template SIDs (support both naming styles)
CONTENT_TEMPLATE_SID_ES = (
    os.getenv("CONTENT_TEMPLATE_SID_ES")
    or os.getenv("WA_CONTENT_SID_ES", "")
)
CONTENT_TEMPLATE_SID_EN = (
    os.getenv("CONTENT_TEMPLATE_SID_EN")
    or os.getenv("WA_CONTENT_SID_EN", "")
)

# Fallback approved body text (if you aren’t using Content Template SIDs)
WA_TEMPLATE_BODY_ES = os.getenv("WA_TEMPLATE_BODY_ES",
    "Hola {{name}} 👋 Soy Luis Carlos. Te invito a apoyar la recaudación de fondos de la banda de Martin HS. ¿Te puedo enviar el enlace?"
)
WA_TEMPLATE_BODY_EN = os.getenv("WA_TEMPLATE_BODY_EN",
    "Hi {{name}} 👋 This is Luis Carlos. I’d like to invite you to support the Martin HS band fundraiser. Can I send you the link?"
)

SMS_BODY = os.getenv("SMS_BODY",
    "Hi {name}, it’s Luis Carlos. We’re raising funds for Martin HS Band 🎺. "
    "Can I send you the link? Reply STOP to opt out."
)

DELAY_SECONDS = float(os.getenv("DELAY_SECONDS", "0.7"))
SENT_LOG  = os.getenv("SENT_LOG",  "sent_log.csv")
ERROR_LOG = os.getenv("ERROR_LOG", "error_log.csv")

# ===============================================================================

def read_rows(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def first_name(row):
    return (row.get("GreetingName") or row.get("FirstName") or row.get("Name") or "friend").strip()

def detect_language(row):
    """
    Returns 'ES' or 'EN'.
    Priority:
      1) Row column 'Language'
      2) Country == MX -> ES, else EN
    """
    lang_raw = (row.get("Language") or row.get("language") or "").strip().lower()
    if lang_raw:
        if lang_raw in ("es", "es-mx", "spanish", "español"):
            return "ES"
        if lang_raw in ("en", "en-us", "english"):
            return "EN"
    country = (row.get("Country") or "").strip().upper()
    if country == "MX":
        return "ES"
    return "EN"

def to_whatsapp_addr(e164):
    return f"whatsapp:{e164}"

def now_iso():
    return datetime.datetime.utcnow().isoformat()

def append_log(path, headers, row_dict):
    exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        if not exists:
            w.writeheader()
        w.writerow({k: row_dict.get(k, "") for k in headers})

def personalize_body(template_text, name):
    return template_text.replace("{{name}}", name)

# ------------------------------- Twilio senders -------------------------------

def send_sms(client, to, body, sms_from):
    return client.messages.create(
        to=to,
        from_=sms_from,
        body=body,
        status_callback=(STATUS_CALLBACK_URL or None)
    )

def send_wa_text_body(client, to_wa, body, wa_from):
    return client.messages.create(
        to=to_wa,
        from_=wa_from,
        body=body,
        status_callback=(STATUS_CALLBACK_URL or None)
    )

def send_wa_content_template(client, to_wa, wa_from, content_sid, variables: dict):
    return client.messages.create(
        to=to_wa,
        from_=wa_from,
        content_sid=content_sid,
        content_variables=json.dumps(variables),
        status_callback=(STATUS_CALLBACK_URL or None)
    )

# ------------------------------- Main CLI logic -------------------------------

def main():
    ap = argparse.ArgumentParser(description="Bulk sender for WhatsApp/SMS from CSV with auto-language template selection")
    ap.add_argument("csv_file", help="Input CSV: whatsapp_contacts.csv or sms_contacts.csv")
    ap.add_argument("mode", choices=["WA", "WA_TEMPLATE", "SMS"],
                    help="WA: plain body (24h window only). WA_TEMPLATE: approved template (Content SID or body). SMS: plain text.")
    ap.add_argument("--start-from", type=int, default=0, help="Row index to start from (0-based)")
    ap.add_argument("--limit", type=int, default=None, help="Max rows to send")
    ap.add_argument("--dry-run", action="store_true", help="Print actions but do not send")
    ap.add_argument("--delay", type=float, default=DELAY_SECONDS, help="Seconds between sends")
    ap.add_argument("--wa-lang", choices=["EN", "ES", "AUTO"], default="AUTO",
                    help="Force WhatsApp template language (EN/ES). Default AUTO (MX→ES, else EN).")
    args = ap.parse_args()

    # Twilio client
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        print("ERROR: Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN env vars.", file=sys.stderr)
        sys.exit(1)
    client = Client(sid, token)

    sms_from = DEFAULT_SMS_FROM
    wa_from = WA_FROM

    if args.mode in ("WA", "WA_TEMPLATE") and not wa_from:
        print("ERROR: Set TWILIO_WHATSAPP_FROM", file=sys.stderr)
        sys.exit(1)
    if args.mode == "SMS" and not sms_from:
        print("ERROR: Set TWILIO_SMS_FROM", file=sys.stderr)
        sys.exit(1)

    rows = read_rows(args.csv_file)
    total = len(rows)
    sent = 0
    start = max(args.start_from, 0)
    end = total if args.limit is None else min(total, start + args.limit)

    print(f"Loaded {total} rows from {args.csv_file}. Sending rows [{start}:{end}) in mode={args.mode}...")
    for idx in range(start, end):
        row = rows[idx]
        name = first_name(row)
        phone = row.get("Phone_E164") or row.get("Phone")
        if not phone:
            print(f"[{idx}] SKIP: no phone for {row.get('Name')}")
            continue

        try:
            if args.mode == "SMS":
                body = SMS_BODY.format(name=name)
                if args.dry_run:
                    print(f"[{idx}] SMS to {phone} :: {body}")
                else:
                    msg = send_sms(client, phone, body, sms_from)
                    print(f"[{idx}] SMS sent to {phone} :: SID {msg.sid}")
                    append_log(SENT_LOG,
                        ["timestamp","sid","name","phone","mode","body","lang"],
                        {"timestamp": now_iso(), "sid": msg.sid, "name": row.get("Name",""),
                         "phone": phone, "mode": "SMS", "body": body, "lang": ""})

            elif args.mode == "WA":
                lang = detect_language(row)
                if args.wa_lang != "AUTO":
                    lang = args.wa_lang
                body = personalize_body(WA_TEMPLATE_BODY_ES if lang=="ES" else WA_TEMPLATE_BODY_EN, name)
                to_wa = to_whatsapp_addr(phone)
                if args.dry_run:
                    print(f"[{idx}] WA TEXT ({lang}) to {to_wa} :: {body}")
                else:
                    msg = send_wa_text_body(client, to_wa, body, wa_from)
                    print(f"[{idx}] WA TEXT ({lang}) sent to {to_wa} :: SID {msg.sid}")
                    append_log(SENT_LOG,
                        ["timestamp","sid","name","phone","mode","body","lang"],
                        {"timestamp": now_iso(), "sid": msg.sid, "name": row.get("Name",""),
                         "phone": phone, "mode": "WA", "body": body, "lang": lang})

            elif args.mode == "WA_TEMPLATE":
                lang = detect_language(row)
                if args.wa_lang != "AUTO":
                    lang = args.wa_lang
                to_wa = to_whatsapp_addr(phone)

                content_sid = CONTENT_TEMPLATE_SID_ES if lang == "ES" else CONTENT_TEMPLATE_SID_EN
                if content_sid:
                    variables = {"1": name}
                    if args.dry_run:
                        print(f"[{idx}] WA TEMPLATE via Content ({lang}) to {to_wa} :: content_sid={content_sid} vars={variables}")
                    else:
                        msg = send_wa_content_template(client, to_wa, wa_from, content_sid, variables)
                        print(f"[{idx}] WA TEMPLATE via Content ({lang}) sent to {to_wa} :: SID {msg.sid}")
                        append_log(SENT_LOG,
                            ["timestamp","sid","name","phone","mode","body","lang"],
                            {"timestamp": now_iso(), "sid": msg.sid, "name": row.get("Name",""),
                             "phone": phone, "mode": "WA_TEMPLATE",
                             "body": f"content_sid={content_sid} vars={variables}", "lang": lang})
                else:
                    body = personalize_body(WA_TEMPLATE_BODY_ES if lang=="ES" else WA_TEMPLATE_BODY_EN, name)
                    if args.dry_run:
                        print(f"[{idx}] WA TEMPLATE (BODY) ({lang}) to {to_wa} :: {body}")
                    else:
                        msg = send_wa_text_body(client, to_wa, body, wa_from)
                        print(f"[{idx}] WA TEMPLATE (BODY) ({lang}) sent to {to_wa} :: SID {msg.sid}")
                        append_log(SENT_LOG,
                            ["timestamp","sid","name","phone","mode","body","lang"],
                            {"timestamp": now_iso(), "sid": msg.sid, "name": row.get("Name",""),
                             "phone": phone, "mode": "WA_TEMPLATE", "body": body, "lang": lang})

            sent += 1
            if idx < end - 1 and args.delay > 0:
                time.sleep(args.delay)
        except Exception as e:
            print(f"[{idx}] ERROR sending to {phone}: {e}", file=sys.stderr)
            append_log(ERROR_LOG,
                ["timestamp","name","phone","mode","error"],
                {"timestamp": now_iso(), "name": row.get("Name",""),
                 "phone": phone, "mode": args.mode, "error": repr(e)}
            )

    print(f"Done. Attempted: {end-start}, Sent (no exception): {sent}")
    if args.dry_run:
        print("Dry run only — no messages were sent.")

if __name__ == "__main__":
    main()
