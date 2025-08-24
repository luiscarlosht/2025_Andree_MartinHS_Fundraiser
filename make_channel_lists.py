#!/usr/bin/env python3
import csv
import sys
from pathlib import Path

INFILE = "contacts_clean_for_whatsapp_fixed.csv"
OUT_WA = "contacts_whatsapp.csv"
OUT_SMS = "contacts_sms.csv"

# Column order we expect / preserve (falls back gracefully if extras exist)
BASE_FIELDS = ["Name", "Phone_E164", "Country", "Channel", "OptIn"]

def load_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        rows = list(rdr)
        fieldnames = rdr.fieldnames or BASE_FIELDS
    return rows, fieldnames

def write_rows(path, rows, fieldnames):
    # Ensure at least the base columns are present (and preserve any extras)
    keep = fieldnames[:]
    for col in BASE_FIELDS:
        if col not in keep:
            keep.append(col)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keep)
        w.writeheader()
        for r in rows:
            w.writerow(r)

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else INFILE
    rows, fields = load_rows(src)

    # Normalize blank/missing columns
    for r in rows:
        r.setdefault("Channel", "")
        r.setdefault("OptIn", "")

    # Build WhatsApp list (force Channel = WhatsApp)
    wa_rows = []
    for r in rows:
        rr = dict(r)
        rr["Channel"] = "WhatsApp"
        wa_rows.append(rr)

    # Build SMS list (force Channel = SMS)
    sms_rows = []
    for r in rows:
        rr = dict(r)
        rr["Channel"] = "SMS"
        sms_rows.append(rr)

    write_rows(OUT_WA, wa_rows, fields)
    write_rows(OUT_SMS, sms_rows, fields)

    print(f"✅ Wrote {len(wa_rows)} rows -> {OUT_WA}")
    print(f"✅ Wrote {len(sms_rows)} rows -> {OUT_SMS}")

if __name__ == "__main__":
    main()
