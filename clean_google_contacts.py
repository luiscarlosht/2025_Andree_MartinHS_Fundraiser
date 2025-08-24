import csv
import re
import sys
from collections import OrderedDict

# ------- TWEAKABLE SETTINGS -------
DEFAULT_US_COUNTRY_CODE = "+1"
DEFAULT_MX_COUNTRY_CODE = "+52"

# Twilio/WhatsApp for Mexico: most use plain +52 + 10 digits.
# If your WhatsApp messages fail for MX mobiles, set this to True to insert a '1' after +52 (legacy behavior in some setups).
ADD_MX_MOBILE_ONE = False
# ---------------------------------

PHONE_COLS = [
    "Phone 1 - Value","Phone 2 - Value","Phone 3 - Value",
    "Phone 4 - Value","Phone 5 - Value","Phone 6 - Value"
]
LABEL_COLS = [
    "Phone 1 - Label","Phone 2 - Label","Phone 3 - Label",
    "Phone 4 - Label","Phone 5 - Label","Phone 6 - Label"
]

def only_digits(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())

def normalize_phone(raw: str):
    """
    Returns (e164_number, country) or (None, None) if not valid.
    Tries to interpret US and MX numbers; passes through other +CC if present.
    Accepts inputs like: (214) 555-1212, 1-214-..., 214.555.1212, +52 55..., 011 52 55...
    """
    if not raw:
        return None, None
    s = raw.strip()

    # Already E.164?
    if s.startswith("+") and len(only_digits(s)) >= 8:
        digits = only_digits(s)
        cc = digits[:2] if s.startswith("+52") else digits[:1]
        country = "MX" if s.startswith("+52") else ("US" if s.startswith("+1") else "INTL")
        # Optionally convert +52xxxxxxxxxx to +521xxxxxxxxxx for MX mobile (rarely needed)
        if country == "MX" and ADD_MX_MOBILE_ONE:
            # if already +521... leave it; if +52 and 10 digits after, insert '1'
            if s.startswith("+52") and not s.startswith("+521"):
                # Keep only country + local digits
                local = digits[2:]  # after 52
                if len(local) == 10:
                    return "+521" + local, "MX"
        return "+" + digits, country

    # 00 international prefix
    if s.startswith("00"):
        digits = only_digits(s[2:])
        if digits.startswith("52"):
            country = "MX"
            local = digits[2:]
            if ADD_MX_MOBILE_ONE and len(local) == 10 and not digits.startswith("521"):
                return "+521" + local, "MX"
            return "+52" + local, "MX"
        return "+" + digits, "INTL"

    digits = only_digits(s)

    # Leading '011' (US intl prefix)
    if digits.startswith("011"):
        d = digits[3:]
        if d.startswith("52"):
            country = "MX"
            local = d[2:]
            if ADD_MX_MOBILE_ONE and len(local) == 10 and not d.startswith("521"):
                return "+521" + local, "MX"
            return "+52" + local, "MX"
        return "+" + d, "INTL"

    # Looks like US-style (10 or 11 with leading 1)
    if len(digits) == 11 and digits.startswith("1"):
        return DEFAULT_US_COUNTRY_CODE + digits[1:], "US"
    if len(digits) == 10:
        # assume US by default if 10 digits and not clearly MX format
        # if you know a subset are MX local 10-digit, move them to a separate list later
        return DEFAULT_US_COUNTRY_CODE + digits, "US"

    # Mexico forms we might see: 12 digits starting 52 or 521
    if digits.startswith("52") and len(digits) in (12, 13):
        local = digits[2:]
        country = "MX"
        if ADD_MX_MOBILE_ONE and not digits.startswith("521") and len(local) == 10:
            return "+521" + local, "MX"
        return "+" + digits, "MX"

    # Fallback: reject if too short/odd
    if len(digits) >= 8:
        return "+" + digits, "INTL"

    return None, None

def pick_best_number(row):
    """
    Prefer labels containing 'Mobile', then 'Cell', then anything valid.
    """
    candidates = []
    for i, col in enumerate(PHONE_COLS):
        val = row.get(col, "").strip()
        if not val:
            continue
        label = (row.get(LABEL_COLS[i], "") or "").lower()
        e164, country = normalize_phone(val)
        if e164:
            score = 2 if ("mobile" in label or "cell" in label or "móvil" in label) else 1
            candidates.append((score, e164, country))
    if not candidates:
        return None, None
    candidates.sort(reverse=True)  # highest score first
    return candidates[0][1], candidates[0][2]

def full_name(row):
    first = (row.get("First Name","") or "").strip()
    last = (row.get("Last Name","") or "").strip()
    nick = (row.get("Nickname","") or "").strip()
    name = " ".join(x for x in [first, last] if x)
    if not name and nick:
        name = nick
    if not name:
        # fallback to any non-empty org or email
        name = (row.get("Organization Name","") or "").strip() or (row.get("E-mail 1 - Value","") or "").strip()
    return name or "Unknown"

def main(in_csv, out_csv):
    with open(in_csv, newline='', encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    out_rows = []
    seen_numbers = set()

    for row in rows:
        name = full_name(row)
        phone, country = pick_best_number(row)
        if not phone:
            continue  # skip contacts with no valid number

        if phone in seen_numbers:
            continue
        seen_numbers.add(phone)

        # Guess channel: use WhatsApp for MX by default; US can be SMS or WhatsApp—start with WhatsApp
        channel = "WhatsApp" if country in ("MX","US") else "WhatsApp"
        out_rows.append(OrderedDict([
            ("Name", name),
            ("Phone", phone),
            ("Country", country or ""),
            ("Channel", channel),
            ("OptIn", "")
        ]))

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Name","Phone","Country","Channel","OptIn"])
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"Wrote {len(out_rows)} contacts to {out_csv}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python clean_contacts.py GoogleContactsLuisCarlosList.csv FundraiserContacts.csv")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
