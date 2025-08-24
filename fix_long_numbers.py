import csv, re, sys
from collections import OrderedDict

INFILE  = "contacts_clean_for_whatsapp.csv"
OUTFILE = "contacts_clean_for_whatsapp_fixed.csv"

# prefer these windows inside long strings
PAT_US = re.compile(r"\+1\d{10}")
# MX can be +52 + 10 digits (common) or +521 + 10 (some carriers)
PAT_MX = re.compile(r"\+52(?:1)?\d{10}")
PAT_ANY_PLUS = re.compile(r"\+\d{8,15}")  # generic E.164-ish window

def pick_window(s):
    s = s.strip()
    if len(re.sub(r"\D","",s)) <= 15:
        return s  # already short enough

    m = PAT_US.search(s)
    if m: return m.group()

    m = PAT_MX.search(s)
    if m: return m.group()

    m = PAT_ANY_PLUS.search(s)
    if m: return m.group()

    # last resort: keep '+' and first 15 digits total
    digits = re.sub(r"\D","",s)
    return "+" + digits[:15] if digits else s

def country_of(e164):
    if e164.startswith("+1"):  return "US"
    if e164.startswith("+52"): return "MX"
    return "INTL"

rows = []
with open(INFILE, newline="", encoding="utf-8") as f:
    r = csv.DictReader(f)
    for row in r:
        ph = row.get("Phone_E164","").strip()
        if not ph:
            continue
        fixed = pick_window(ph)
        row["Phone_E164"] = fixed
        row["Country"] = country_of(fixed)
        rows.append(row)

# de-dupe by phone
unique = OrderedDict()
for row in rows:
    key = row["Phone_E164"]
    if key not in unique:
        unique[key] = row

with open(OUTFILE, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["Name","Phone_E164","Country","Channel","OptIn"])
    w.writeheader()
    w.writerows(unique.values())

print(f"✅ Wrote {len(unique)} rows -> {OUTFILE}")
