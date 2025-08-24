#!/usr/bin/env python3
import csv, re, sys, unicodedata
from pathlib import Path

INFILE  = str(Path.home() / "contacts_raw.tsv")
OUTFILE = str(Path.home() / "contacts_clean_for_whatsapp.csv")

# Basic helpers
def strip_accents(s):
    try:
        return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))
    except Exception:
        return s

def normalize_name(s):
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s

# Pull only digits, keep leading '+'
def digits_plus(s):
    s = s or ""
    s = s.strip()
    s = s.replace("—", "-")
    s = s.replace("–", "-")
    s = s.replace("—", "-")
    # keep + and digits only
    return re.sub(r"(?!^\+)[^\d]", "", s)

# Split concatenated phone numbers:
# Examples seen:
#   +1817307051518175648524   -> two US numbers stuck together
#   +21420774072142077407     -> two 11/10-digit sequences smashed
#   12144777343               -> valid US
# Strategy:
#  - If there is a '+' inside: split at every '+'
#  - Else, greedily extract all 10-15 digit sequences
def split_phones(raw):
    s = (raw or "").strip()
    if not s:
        return []
    # Normalize separators to spaces
    s = s.replace(":::", " ").replace("/", " ").replace("\\", " ")
    # If we see multiple '+', split
    if s.count('+') > 1:
        parts = [p.strip() for p in re.split(r"\s*\+\s*", s)]
        parts = ["+"+p for p in parts if p]
    else:
        parts = [s]

    numbers = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # If it has a '+', keep only + and digits
        if p.startswith('+'):
            p = '+' + re.sub(r"\D", "", p[1:])
            if len(p) >= 5:
                numbers.append(p)
        else:
            # No plus: extract long digit runs (10-15)
            for m in re.finditer(r"\d{10,15}", p):
                numbers.append(m.group(0))
    return numbers

# Normalize to E.164 for a couple of common cases
def to_e164(n):
    n = n.strip()
    if not n: return None
    # Already looks like E.164
    if n.startswith('+'):
        return n
    # Assume US if 10 or 11 starting with '1'
    if re.fullmatch(r"\d{10}", n):
        return "+1" + n
    if re.fullmatch(r"1\d{10}", n):
        return "+" + n
    # Mexico often provided with +52 already; if 13 digits starting with 52:
    if re.fullmatch(r"52\d{10,12}", n):
        return "+" + n
    # fall back: prefix + if 11-15 digits
    if re.fullmatch(r"\d{11,15}", n):
        return "+" + n
    return None

def infer_country(e164):
    if not e164: return ""
    if e164.startswith("+1"): return "US"
    if e164.startswith("+52"): return "MX"
    return "INTL"

def is_likely_mobile(e164):
    # Heuristic only; WhatsApp generally works with E.164 for mobiles.
    # We won’t try carrier DB; just accept for +1/+52.
    return e164.startswith("+1") or e164.startswith("+52") or e164.startswith("+5") or e164.startswith("+2") or e164.startswith("+3") or e164.startswith("+4") or e164.startswith("+6") or e164.startswith("+7") or e164.startswith("+8") or e164.startswith("+9")

# Try reading tab-delimited first, then CSV as a fallback
def read_rows(path):
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    # Decide delimiter by header
    header_line = text.splitlines()[0] if text else ""
    if header_line.count("\t") >= 2:
        dialect = "excel-tab"
    else:
        dialect = "excel"

    f = Path(path).open("r", encoding="utf-8", errors="ignore", newline="")
    rdr = csv.DictReader(f, dialect=dialect)
    rows = list(rdr)
    f.close()
    return rows

def main():
    rows = read_rows(INFILE)

    # Try to map probable column names (case-insensitive)
    def find_col(name_opts):
        lower_map = {k.lower(): k for k in rows[0].keys()} if rows else {}
        for o in name_opts:
            if o.lower() in lower_map:
                return lower_map[o.lower()]
        return None

    name_col  = find_col(["Name", "Full Name", "First Name", "File As"])
    phone_col = find_col(["Phone", "Phone 1 - Value", "Mobile", "Primary Phone"])
    chan_col  = find_col(["Channel"])
    country_col = find_col(["Country"])
    optin_col = find_col(["OptIn", "Opt In", "Opt-in"])

    cleaned = []
    seen_numbers = set()

    for r in rows:
        raw_name  = normalize_name(strip_accents(r.get(name_col, "") if name_col else ""))
        raw_phone = r.get(phone_col, "") if phone_col else ""
        raw_chan  = (r.get(chan_col, "") if chan_col else "WhatsApp") or "WhatsApp"
        raw_country = (r.get(country_col, "") if country_col else "").strip().upper()
        raw_optin = (r.get(optin_col, "") if optin_col else "").strip()

        # Split phones and normalize each
        candidates = []
        for piece in split_phones(raw_phone):
            dp = digits_plus(piece)
            if not dp: continue
            candidates.append(dp)

        if not candidates:
            # Skip rows with no usable phone
            continue

        for cand in candidates:
            e164 = to_e164(cand)
            if not e164: 
                continue
            if not is_likely_mobile(e164):
                continue
            # De-dup on number
            if e164 in seen_numbers:
                continue
            seen_numbers.add(e164)

            country = infer_country(e164)
            channel = "WhatsApp"  # we’re prepping for WA
            optin   = raw_optin or ""  # leave blank if unknown

            cleaned.append({
                "Name": raw_name or "",
                "Phone_E164": e164,
                "Country": country,
                "Channel": channel,
                "OptIn": optin
            })

    # Sort for sanity
    cleaned.sort(key=lambda x: (x["Country"], x["Name"] or x["Phone_E164"]))

    # Write output CSV ready for import to your sending pipeline
    fieldnames = ["Name", "Phone_E164", "Country", "Channel", "OptIn"]
    with open(OUTFILE, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(cleaned)

    print(f"✅ Wrote {len(cleaned)} cleaned contacts -> {OUTFILE}")

if __name__ == "__main__":
    main()
