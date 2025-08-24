#!/usr/bin/env python3
import csv, re, sys
from collections import OrderedDict
from pathlib import Path

# ------- TWEAKABLE -------
DEFAULT_US_CC = "+1"
DEFAULT_MX_CC = "+52"
ADD_MX_MOBILE_ONE = False   # rarely needed
INFILE  = str(Path.home() / "contacts_raw.tsv")   # or pass via argv[1]
OUTFILE = str(Path.home() / "contacts_clean_for_whatsapp.csv")  # or argv[2]
# -------------------------

PHONE_COLS = [
    "Phone 1 - Value","Phone 2 - Value","Phone 3 - Value",
    "Phone 4 - Value","Phone 5 - Value","Phone 6 - Value"
]
LABEL_COLS = [
    "Phone 1 - Label","Phone 2 - Label","Phone 3 - Label",
    "Phone 4 - Label","Phone 5 - Label","Phone 6 - Label"
]

# Regexes to find possible phones inside messy text:
RE_E164 = re.compile(r"\+\d{8,15}")
RE_US_10_11 = re.compile(r"(?<!\d)(1?\d{10})(?!\d)")
RE_MX_12_13 = re.compile(r"(?<!\d)(52\d{10}|521\d{10})(?!\d)")

def only_digits(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())

def normalize_phone(raw: str):
    """
    Return (e164, country) or (None, None).
    Handles +E.164, US national (10 or 11 with leading 1), and MX 52/521 + 10.
    """
    if not raw: return None, None
    s = raw.strip()

    # Already E.164?
    if s.startswith("+"):
        d = only_digits(s)
        if len(d) < 8: return None, None
        if d.startswith("1"):
            return "+"+d, "US"
        if d.startswith("52"):
            local = d[2:]
            if ADD_MX_MOBILE_ONE and not d.startswith("521") and len(local)==10:
                return "+521"+local, "MX"
            return "+"+d, "MX"
        return "+"+d, "INTL"

    d = only_digits(s)
    if not d: return None, None

    # MX 52/521 + 10 digits
    if (d.startswith("52") and len(d) in (12,13)):
        local = d[2:]
        if ADD_MX_MOBILE_ONE and not d.startswith("521") and len(local)==10:
            return "+521"+local, "MX"
        return "+"+d, "MX"

    # US national
    if len(d)==11 and d.startswith("1"):
        return DEFAULT_US_CC + d[1:], "US"
    if len(d)==10:
        return DEFAULT_US_CC + d, "US"

    # Generic INTL if looks long enough
    if len(d) >= 8:
        return "+"+d, "INTL"
    return None, None

def extract_phone_candidates(text: str):
    """
    From a messy string, extract multiple phone-like chunks.
    Prioritize explicit +E.164, then MX (52/521...), then US 10/11-digit.
    Also split on obvious separators (commas, slashes, :::, pipes).
    """
    if not text: return []

    pieces = re.split(r"[,\|/;:\t]|:::|\s{2,}", text)
    raw_hits = []

    # 1) Gather explicit +E.164
    raw_hits += RE_E164.findall(text)

    # 2) MX style 52/521 + 10
    raw_hits += RE_MX_12_13.findall(text)

    # 3) US 10/11 contiguous digits
    raw_hits += RE_US_10_11.findall(text)

    # 4) Also scan each piece for loose phones (keeps (xxx) yyy-zzzz forms)
    LOOSE = re.compile(r"\+?\d[\d\-\s\(\)\.]{6,}\d")
    for p in pieces:
        raw_hits += LOOSE.findall(p)

    # Normalize & uniquify preserving order
    seen = set()
    out = []
    for h in raw_hits:
        e164, country = normalize_phone(h)
        if e164 and e164 not in seen:
            seen.add(e164)
            out.append((e164, country))
    return out

def pick_best_number(row):
    """
    Prefer numbers from columns whose label contains Mobile/Cell/Móvil.
    If multiple found in a single cell, take the first valid after normalization.
    """
    mobile_keywords = ("mobile","cell","móvil","m\u00f3vil")  # cover accents
    best = None

    # First pass: look for mobile-labelled columns
    for i, col in enumerate(PHONE_COLS):
        val = (row.get(col, "") or "").strip()
        if not val: continue
        label = (row.get(LABEL_COLS[i], "") or "").lower()
        cands = extract_phone_candidates(val)
        if not cands: continue
        if any(k in label for k in mobile_keywords):
            return cands[0]  # (e164, country)
        if best is None:
            best = cands[0]

    return best if best else (None, None)

def full_name(row):
    first = (row.get("First Name","") or "").strip()
    last  = (row.get("Last Name","")  or "").strip()
    nick  = (row.get("Nickname","")   or "").strip()
    name = " ".join(x for x in [first, last] if x)
    if not name and nick:
        name = nick
    if not name:
        name = (row.get("Organization Name","") or "").strip() or (row.get("E-mail 1 - Value","") or "").strip()
    return name or "Unknown"

def read_rows(path):
    # Read TSV/CSV with forgiving dialect
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    # guess delimiter by header
    delim = "\t" if "\t" in text.splitlines()[0] else ","
    rows = []
    for row in csv.DictReader(text.splitlines(), delimiter=delim):
        rows.append(row)
    return rows

def main():
    in_path  = sys.argv[1] if len(sys.argv) > 1 else INFILE
    out_path = sys.argv[2] if len(sys.argv) > 2 else OUTFILE

    rows = read_rows(in_path)
    out_rows = []
    seen = set()

    for row in rows:
        name = full_name(row)
        phone, country = pick_best_number(row)
        if not phone: continue
        if phone in seen: continue
        seen.add(phone)

        channel = "WhatsApp" if country in ("US","MX","INTL") else "WhatsApp"
        out_rows.append(OrderedDict([
            ("Name", name),
            ("Phone_E164", phone),
            ("Country", country or ""),
            ("Channel", channel),
            ("OptIn", "")
        ]))

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Name","Phone_E164","Country","Channel","OptIn"])
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"✅ Wrote {len(out_rows)} cleaned contacts -> {out_path}")

if __name__ == "__main__":
    main()
