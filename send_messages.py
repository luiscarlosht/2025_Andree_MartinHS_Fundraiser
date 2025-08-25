#!/usr/bin/env python3
import argparse, csv, os, sys, time, datetime
from twilio.rest import Client

# ---------------------------- CONFIG ----------------------------
WA_TEMPLATE_BODY = (
    "Hola {{name}} 👋 Soy Luis Carlos. "
    "Te invito a apoyar la recaudación de fondos de la banda de Martin HS. "
    "¿Te puedo enviar el enlace?"
)

SMS_BODY = (
    "Hi {name}, it’s Luis Carlos. We’re raising funds for Martin HS Band 🎺. "
    "Can I send you the link? Reply STOP to opt out."
)

# Optional: public status callback URL (Flask route /status)
STATUS_CALLBACK_URL = os.getenv("STATUS_CALLBACK_URL")  # leave unset = no callback

# Defaults if env vars missing
DEFAULT_SMS_FROM = "+18772354306"   # your toll-free number
DELAY_SECONDS = 0.7

# CSV logs
SENT_LOG = os.getenv("SENT_LOG", "sent_log.csv")
ERROR_LOG = os.getenv("ERROR_LOG", "error_log.csv")
# ----------------------------------------------------------------

def read_rows(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def first_name(row):
    return (row.get("GreetingName") or row.get("FirstName") or row.get("Name") or "friend").strip()

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

def send_sms(client, to, body, sms_from):
    kwargs = {}
    if STATUS_CALLBACK_URL:
        kwargs["status_callback"] = STATUS_CALLBACK_URL
    return client.messages.create(to=to, from_=sms_from, body=body, **kwargs)

def send_wa_text(client, to_wa, body, wa_from):
    kwargs = {}
    if STATUS_CALLBACK_URL:
        kwargs["status_callback"] = STATUS_CALLBACK_URL
    return client.messages.create(to=to_wa, from_=wa_from, body=body, **kwargs)

def personalize_template(template_text, name):
    return template_text.replace("{{name}}", name)

def send_wa_template_simple_body(client, to_wa, wa_from, name):
    body = personalize_template(WA_TEMPLATE_BODY, name)
    kwargs = {}
    if STATUS_CALLBACK_URL:
        kwargs["status_callback"] = STATUS_CALLBACK_URL
    return client.messages.create(to=to_wa, from_=wa_from, body=body, **kwargs)

def main():
    ap = argparse.ArgumentParser(description="Bulk sender for WhatsApp/SMS from CSV")
    ap.add_argument("csv_file", help="Input CSV: whatsapp_contacts.csv or sms_contacts.csv")
    ap.add_argument("mode", choices=["WA", "WA_TEMPLATE", "SMS"], help="Send mode")
    ap.add_argument("--start-from", type=int, default=0, help="Row index to start from (0-based)")
    ap.add_argument("--limit", type=int, default=None, help="Max rows to send")
    ap.add_argument("--dry-run", action="store_true", help="Print actions but do not send")
    ap.add_argument("--delay", type=float, default=DELAY_SECONDS, help="Seconds between sends")
    args = ap.parse_args()

    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        print("ERROR: Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN env vars.", file=sys.stderr)
        sys.exit(1)
    client = Client(sid, token)

    sms_from = os.getenv("TWILIO_SMS_FROM", DEFAULT_SMS_FROM)
    wa_from = os.getenv("TWILIO_WHATSAPP_FROM")

    if args.mode in ("WA", "WA_TEMPLATE") and not wa_from:
        print("ERROR: Set TWILIO_WHATSAPP_FROM (e.g., whatsapp:+14155238886)", file=sys.stderr)
        sys.exit(1)

    rows = read_rows(args.csv_file)
    total = len(rows)
    start, end = max(args.start_from, 0), total if args.limit is None else min(total, args.start_from + args.limit)

    print(f"Loaded {total} rows from {args.csv_file}. Sending rows [{start}:{end}) in mode={args.mode}...")
    sent = 0

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
                    append_log(SENT_LOG, ["timestamp","sid","name","phone","mode","body"],
                               {"timestamp": now_iso(),"sid":msg.sid,"name":row.get("Name",""),"phone":phone,"mode":"SMS","body":body})

            elif args.mode == "WA":
                body = personalize_template(WA_TEMPLATE_BODY, name)
                to_wa = to_whatsapp_addr(phone)
                if args.dry_run:
                    print(f"[{idx}] WA TEXT to {to_wa} :: {body}")
                else:
                    msg = send_wa_text(client, to_wa, body, wa_from)
                    print(f"[{idx}] WA TEXT sent to {to_wa} :: SID {msg.sid}")
                    append_log(SENT_LOG, ["timestamp","sid","name","phone","mode","body"],
                               {"timestamp": now_iso(),"sid":msg.sid,"name":row.get("Name",""),"phone":phone,"mode":"WA","body":body})

            elif args.mode == "WA_TEMPLATE":
                to_wa = to_whatsapp_addr(phone)
                if args.dry_run:
                    preview = personalize_template(WA_TEMPLATE_BODY, name)
                    print(f"[{idx}] WA TEMPLATE to {to_wa} :: {preview}")
                else:
                    msg = send_wa_template_simple_body(client, to_wa, wa_from, name)
                    print(f"[{idx}] WA TEMPLATE sent to {to_wa} :: SID {msg.sid}")
                    append_log(SENT_LOG, ["timestamp","sid","name","phone","mode","body"],
                               {"timestamp": now_iso(),"sid":msg.sid,"name":row.get("Name",""),"phone":phone,"mode":"WA_TEMPLATE","body":personalize_template(WA_TEMPLATE_BODY,name)})

            sent += 1
            if idx < end - 1 and args.delay > 0:
                time.sleep(args.delay)

        except Exception as e:
            print(f"[{idx}] ERROR sending to {phone}: {e}", file=sys.stderr)
            append_log(ERROR_LOG, ["timestamp","name","phone","mode","error"],
                       {"timestamp": now_iso(),"name":row.get("Name",""),"phone":phone,"mode":args.mode,"error":repr(e)})

    print(f"Done. Attempted: {end-start}, Sent (no exception): {sent}")
    if args.dry_run:
        print("Dry run only — no messages were sent.")

if __name__ == "__main__":
    main()
