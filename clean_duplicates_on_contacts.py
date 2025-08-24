#!/usr/bin/env python3
import csv, re, sys
from pathlib import Path
from collections import OrderedDict

# --------- SETTINGS ----------
DEFAULT_US_CC = "+1"
DEFAULT_MX_CC = "+52"
ADD_MX_MOBILE_ONE = False   # rarely needed nowadays
# -----------------------------

# Google Contacts schema columns (if present)
PHONE_COLS = [f"Phone {i} - Value" for i in range(1,7)]
LABEL_COLS = [f"Phone {i} - Label" for i in range(1,7)]

def only_digits(s:str) -> str:
    return "".join(ch for ch in s if ch.isdigit())

def country_from_e164(e:str) -> str:
    if e.startswith("+1"): return "US"
    if e.startswith("+52"): return "MX"
    return "INTL"

def normalize_phone(raw:str):
    """Normalize a single number-ish string to E.164 if possible."""
    if not raw: return None
    s = raw.strip()
    if s.startswith("+"):
        d = only_digits(s)
        if len(d) < 8: return None
        # Handle +52 mobile legacy insertion if asked
        if d.startswith("52"):
            local = d[2:]
            if ADD_MX_MOBILE_ONE and not d.startswith("521") and len(local)==10:
                return "+521"+local
            return "+"+d
        return "+"+d
    d = only_digits(s)
    if not d: return None

    # Mexico 52/521 + 10 digits
    if (d.startswith("52") and len(d) in (12,13)):
        local = d[2:]
        if ADD_MX_MOBILE_ONE and not d.startswith("521") and len(local)==10:
            return "+521"+local
        return "+"+d

    # US national 10 or 11 (leading 1)
    if len(d)==11 and d.startswith("1"):
        return DEFAULT_US_CC + d[1:]
    if len(d)==10:
        return DEFAULT_US_CC + d

    # Fallback: if it looks long enough, keep as intl
    if len(d) >= 8:
        return "+"+d
    return None

def sliding_candidates_from_digits(digits:str):
    """
    Inside a big glued digit string, pull out plausible windows:
      - 11-digit windows starting with '1' -> +1 + 10
      - 12-digit windows starting with '52' -> +52 + 10
      - 13-digit windows starting with '521' -> +521 + 10
    """
    out = []
    n = len(digits)
    for i in range(n):
        w11 = digits[i:i+11]
        if len(w11)==11 and w11.startswith("1"):
            out.append("+1"+w11[1:])
        w12 = digits[i:i+12]
        if len(w12)==12 and w12.startswith("52"):
            out.append("+"+w12)
        w13 = digits[i:i+13]
        if len(w13)==13 and w13.startswith("521"):
            out.append("+"+w13)
    # preserve order, dedupe
    seen=set(); uniq=[]
    for p in out:
        if p not in seen:
            seen.add(p); uniq.append(p)
    return uniq

def extract_phone_candidates(text:str):
    """
    Find one or more candidate numbers inside messy text.
    Prefer explicit +1XXXXXXXXXX or +52XXXXXXXXXX tokens.
    Also split when multiple '+' exist.
    """
    if not text: return []

    # 1) direct tokens for US/MX with a leading '+'
    tokens = re.findall(r"\+1\d{10}|\+521?\d{10}", text)
    # 2) if multiple '+' segments, try each segment independently
    if text.count("+") > 1:
        parts = [p for p in re.split(r"(?=\+)", text) if p.strip()]
        for p in parts:
            tokens += re.findall(r"\+1\d{10}|\+521?\d{10}", p)

    # 3) if still nothing or value looks glued, scan digit windows
    if not tokens or len(only_digits(text)) > 15:
        digits = only_digits(text)
        tokens += sliding_candidates_from_digits(digits)

    # 4) fallback: try normalizing whole thing
    e = normalize_phone(text)
    if e and e not in tokens:
        tokens.append(e)

    # Dedup, keep order
    seen=set(); out=[]
    for t in tokens:
        if t and t not in seen:
            seen.add(t); out.append(t)
    return out

def pick_best_from_simple_row(row):
    """
    For schema: Name | Phone | ...
    Use the first valid candidate extracted from Phone.
    """
    phone_field = (row.get("Phone","") or "").strip()
    if not phone_field: return None
    cands = extract_phone_candidates(phone_field)
    return cands[0] if cands else None

def pick_best_from_google_row(row):
    """
    For Google Contacts schema with Phone n - Value columns.
    Prefer columns labeled Mobile/Cell/Móvil.
    If a cell has multiple glued numbers, extract the first valid candidate.
    """
    mobile_keywords = ("mobile","cell","móvil","m\u00f3vil")
    best=None
    for i, col in enumerate(PHONE_COLS):
        val = (row.get(col,"") or "").strip()
        if not val: continue
        label = (row.get(LABEL_COLS[i],"") or "").lower()
        cands = extract_phone_candidates(val)
        if not cands: continue
        if any(k in label for k in mobile_keywords):
            return cands[0]
        if best is None: best = cands[0]
    return best

def full_name(row):
    # Works for both schemas
    name = (row.get("Name","") or "").strip()
    if name: return name
    first = (row.get("First Name","") or "").strip()
    last  = (row.get("Last Name","")  or "").strip()
    nick  = (row.get("Nickname","")   or "").strip()
    n = " ".join(x for x in [first,last] if x) or nick
    if n: return n
    org = (row.get("Organization Name","") or "").strip()
    email = (row.get("E-mail 1 - Value","") or "").strip()
    return n or org or email or "Unknown"

def read_rows(path):
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    header = text.splitlines()[0]
    delim = "\t" if "\t" in header and (header.count("\t") >= header.count(",")) else ","
    return list(csv.DictReader(text.splitlines(), delimiter=delim))

def main():
    if len(sys.argv) < 3:
        print("Usage: python clean_contacts_any_schema.py INPUT(.csv|.tsv) OUTPUT.csv")
        sys.exit(1)
    in_path, out_path = sys.argv[1], sys.argv[2]

    rows = read_rows(in_path)
    out_rows = []
    seen=set()

    simple_schema = "Phone" in rows[0]

    for row in rows:
        name = full_name(row)
        phone = pick_best_from_simple_row(row) if simple_schema else pick_best_from_google_row(row)
        if not phone: continue
        if phone in seen: continue
        seen.add(phone)
        country = country_from_e164(phone)
        out_rows.append(OrderedDict([
            ("Name", name),
            ("Phone_E164", phone),
            ("Country", country),
            ("Channel", "WhatsApp"),
            ("OptIn", "")
        ]))

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["Name","Phone_E164","Country","Channel","OptIn"])
        w.writeheader(); w.writerows(out_rows)
    print(f"✅ Wrote {len(out_rows)} cleaned contacts -> {out_path}")

if __name__ == "__main__":
    main()
