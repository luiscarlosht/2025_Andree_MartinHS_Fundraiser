#!/usr/bin/env python3
import argparse, csv, json, os, sys, time, datetime
from pathlib import Path
from twilio.rest import Client

# ---------------------------- CONFIG YOU'LL TWEAK ----------------------------
# WhatsApp template body (must match an approved template; {{name}} will be substituted):
WA_TEMPLATE_BODY = (
    "Hola {{name}} 👋 Soy Luis Carlos. "
    "Te invito a apoyar la recaudación de fondos de la banda de Martin HS. "
    "¿Te puedo enviar el enlace?"
)

# SMS body — personalize with {name}:
SMS_BODY = (
    "Hi {name}, it’s Luis Carlos. We’re raising funds for Martin HS Band 🎺. "
    "Can I send you the link? Reply STOP to opt out."
)

# Your public status callback URL (Flask route /twilio/status)
STATUS_CALLBACK_URL = os.getenv("STATUS_CALLBACK_URL", "https://YOUR_DOMAIN/twilio/status")

# Default SMS FROM if env var is missing (you asked for +1 877 235 4306)
DEFAULT_SMS_FROM = "+18772354306"

# Delay between API calls (seconds) to avoid rate spikes
DELAY_SECONDS = 0.7

# CSV logs
SENT_LOG = os.getenv("SENT_LOG", "sent_log.csv")
ERROR_LOG = os.getenv("ERROR_LOG", "error_log.csv")
# ---------------------------------------------------------------------------

def read_rows(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def first_name(row):
    # Our CSVs have both GreetingName and FirstName — prefer GreetingName
    return (row.get("GreetingName") or row.get("FirstName") or row.get("Name") or "friend").strip()

def to_whatsapp_addr(e164):
    # Twilio expects 'whatsapp:+1...' format for WA; SMS is just '+1...'
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

def send_sms(client, to, body, sms_from):
    return client.messages.create(
        to=to,
        from_=sms_from,
        body=body,
        status_callback=STATUS_CALLBACK_URL or None
    )

def send_wa_text(client, to_wa, body, wa_from):
    # Valid only if you’re inside the 24h session window with the user.
    return client.messages.create(
        to=to_wa,
        from_=wa_from,
        body=body,
        status_callback=STATUS_CALLBACK_URL or None
    )

def personalize_template(template_text, name):
    # Replace {{name}} tokens in WA template body
    return template_text.replace("{{name}}", name)

def send_wa_template_simple_body(client, to_wa, wa_from, name):
    # Simplest: send the approved text with the substituted variable.
    body = personalize_template(WA_TEMPLATE_BODY, name)
    return client.messages.create(
        to=to_wa,
        from_=wa_from,
        body=body,
        status_callback=STATUS_CALLBACK_URL or None
    )

def main():
    ap = argparse.ArgumentParser(description="Bulk sender for WhatsApp/SMS from CSV")
    ap.add_argument("csv_file", help="Input CSV: whatsapp_contacts.csv or sms_contacts.csv")
    ap.add_argument("mode", choices=["WA", "WA_TEMPLATE", "SMS"], help="Send mode")
    ap.add_argument("--start-from", type=int, default=0, help="Row index to start from (0-based)")
    ap.add_argument("--limit", type=int, default=None, help="Max rows to send")
    ap.add_argument("--dry-run", action="store_true", help="Print actions but do not send")
    ap.add_argument("--delay", type=float, default=DELAY_SECONDS, help="Seconds between sends")
    args = ap.parse_args()

    # Twilio client
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        print("ERROR: Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN env vars.", file=sys.stderr)
        sys.exit(1)
    client = Client(sid, token)

    sms_from = os.getenv("TWILIO_SMS_FROM", DEFAULT_SMS_FROM)
    wa_from = os.getenv("TWILIO_WHATSAPP_FROM")  # e.g., "whatsapp:+14155238886"

    if args.mode in ("WA", "WA_TEMPLATE") and not wa_from:
        print("ERROR: Set TWILIO_WHATSAPP_FROM (e.g., whatsapp:+14155238886)", file=sys.stderr)
        sys.exit(1)
    if args.mode == "SMS" and not sms_from:
        print("ERROR: Set TWILIO_SMS_FROM (e.g., +12145550123)", file=sys.stderr)
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
        phone = row.get("Phone_E164") or row.get("Phone")  # support both schemas
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
                        ["timestamp","sid","name","phone","mode","body"],
                        {"timestamp": now_iso(), "sid": msg.sid, "name": row.get("Name",""), "phone": phone, "mode": "SMS", "body": body}
                    )

            elif args.mode == "WA":
                # Plain WA text (only valid if session is open)
                body = personalize_template(WA_TEMPLATE_BODY, name)
                to_wa = to_whatsapp_addr(phone)
                if args.dry_run:
                    print(f"[{idx}] WA TEXT to {to_wa} :: {body}")
                else:
                    msg = send_wa_text(client, to_wa, body, wa_from)
                    print(f"[{idx}] WA TEXT sent to {to_wa} :: SID {msg.sid}")
                    append_log(SENT_LOG,
                        ["timestamp","sid","name","phone","mode","body"],
                        {"timestamp": now_iso(), "sid": msg.sid, "name": row.get("Name",""), "phone": phone, "mode": "WA", "body": body}
                    )

            elif args.mode == "WA_TEMPLATE":
                # Recommended for first outreach – uses your *approved* wording
                to_wa = to_whatsapp_addr(phone)
                if args.dry_run:
                    body_preview = personalize_template(WA_TEMPLATE_BODY, name)
                    print(f"[{idx}] WA TEMPLATE to {to_wa} :: {body_preview}")
                else:
                    msg = send_wa_template_simple_body(client, to_wa, wa_from, name)
                    print(f"[{idx}] WA TEMPLATE sent to {to_wa} :: SID {msg.sid}")
                    append_log(SENT_LOG,
                        ["timestamp","sid","name","phone","mode","body"],
                        {"timestamp": now_iso(), "sid": msg.sid, "name": row.get("Name",""), "phone": phone, "mode": "WA_TEMPLATE", "body": personalize_template(WA_TEMPLATE_BODY, name)}
                    )

            sent += 1
            if idx < end - 1 and args.delay > 0:
                time.sleep(args.delay)
        except Exception as e:
            print(f"[{idx}] ERROR sending to {phone}: {e}", file=sys.stderr)
            append_log(ERROR_LOG,
                ["timestamp","name","phone","mode","error"],
                {"timestamp": now_iso(), "name": row.get("Name",""), "phone": phone, "mode": args.mode, "error": repr(e)}
            )

    print(f"Done. Attempted: {end-start}, Sent (no exception): {sent}")
    if args.dry_run:
        print("Dry run only — no messages were sent.")

if __name__ == "__main__":
    main()
