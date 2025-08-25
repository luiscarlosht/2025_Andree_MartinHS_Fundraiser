#!/usr/bin/env python3
import csv
import sys
import re
from pathlib import Path

# Heuristics to extract a friendly first name
def derive_first_name(full_name: str) -> str:
    if not full_name:
        return ""
    name = full_name.strip()

    # If it's something like "214-477-7343", don't use it as a name
    if re.fullmatch(r"[+()\-.\s0-9]+", name):
        return ""

    # Remove leading prefixes and common clutter
    name = re.sub(r"^(mr|mrs|ms|dr|ing\.|sr|sra|srta|ing|lic)\.?[\s,]+", "", name, flags=re.IGNORECASE)

    # If there’s a comma, take the part before comma as the likely first token
    if "," in name:
        name = name.split(",", 1)[0].strip()

    # Split by whitespace; take the first alphanumeric token
    parts = [p for p in re.split(r"\s+", name) if p]
    if not parts:
        return ""

    first = parts[0]

    # Strip non-letters around edges (e.g., "“John”")
    first = re.sub(r"^[^A-Za-zÁÉÍÓÚÑáéíóúÜü]+|[^A-Za-zÁÉÍÓÚÑáéíóúÜü]+$", "", first)
    return first

def build_greeting_name(first_name: str) -> str:
    if first_name:
        return first_name
    # Fallbacks if no first name could be derived
    return "amig@"  # neutral friendly Spanish; change to "friend" if you prefer English

def prepare_lists(in_csv: str,
                  out_master: str,
                  out_whatsapp: str,
                  out_sms: str):
    with open(in_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Ensure expected columns exist; if missing, create
    base_fields = list(reader.fieldnames or [])
    for col in ["FirstName", "GreetingName"]:
        if col not in base_fields:
            base_fields.append(col)

    # Add FirstName + GreetingName
    enriched = []
    for r in rows:
        name = (r.get("Name") or "").strip()
        first = derive_first_name(name)
        greeting = build_greeting_name(first)
        r["FirstName"] = first
        r["GreetingName"] = greeting
        enriched.append(r)

    # Write master
    with open(out_master, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=base_fields)
        writer.writeheader()
        writer.writerows(enriched)

    # Split
    whatsapp_rows = [r for r in enriched if (r.get("Channel") or "").strip().lower() == "whatsapp"]

    sms_rows = []
    for r in enriched:
        if (r.get("Country") or "").strip().upper() in ("US", "MX"):
            r2 = r.copy()
            r2["Channel"] = "SMS"
            sms_rows.append(r2)

    # Write WhatsApp
    with open(out_whatsapp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=base_fields)
        writer.writeheader()
        writer.writerows(whatsapp_rows)

    # Write SMS
    with open(out_sms, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=base_fields)
        writer.writeheader()
        writer.writerows(sms_rows)

    print(f"✅ Master: {len(enriched)} -> {out_master}")
    print(f"✅ WhatsApp: {len(whatsapp_rows)} -> {out_whatsapp}")
    print(f"✅ SMS (US+MX): {len(sms_rows)} -> {out_sms}")

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python prepare_contact_lists.py <in_csv> <out_master> <out_whatsapp> <out_sms>")
        print("Example:")
        print("  python prepare_contact_lists.py contacts_clean_for_whatsapp_fixed.csv "
              "contacts_with_greeting.csv whatsapp_contacts.csv sms_contacts.csv")
        sys.exit(1)

    prepare_lists(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
