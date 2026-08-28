"""Rebuild reviews.json from the Shopify CSV export the user supplied.

That export is the source of truth for name/date/text. Country is not in it,
so it is looked up from the listing by review id - the ids in the export are
Shopify's own review content ids, which the listing markup carries too.
"""
import io
import json
import re
import time
import urllib.request

SRC = "reviews_export.ts"
OUT = r"c:\Users\sarth\Desktop\Landing Page OE\reviews.json"
BRANDS = r"c:\Users\sarth\Desktop\Landing Page OE\brands.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) landing-page-review-sync"}

src = io.open(SRC, encoding="utf-8").read()

BLOCK = re.compile(
    r'\{\s*id:\s*"(\d+)",\s*name:\s*"((?:[^"\\]|\\.)*)",\s*date:\s*"([^"]*)",\s*'
    r'rating:\s*(\d+),\s*content:\s*"((?:[^"\\]|\\.)*)",',
    re.S,
)

entries = []
for rid, name, date, rating, content in BLOCK.findall(src):
    name = json.loads('"%s"' % name)
    content = json.loads('"%s"' % content)
    content = re.sub(r"\s+", " ", content.replace("\\n", " ")).strip()
    month, rest = date.split(" ", 1)
    entries.append({
        "id": rid,
        "name": name,
        "date": "%s %s" % (month.capitalize(), rest),
        "rating": int(rating),
        "quote": content,
    })

print("parsed %d entries from the export" % len(entries))
assert len(entries) == src.count('    id: "'), "regex missed some blocks"

# ---- country, by review id, from the listing -----------------------------
base = "https://apps.shopify.com/clickpost-order-edit-cancel/reviews"
REVIEW = re.compile(r'data-review-content-id="(\d+)"(.*?)(?=data-review-content-id="|\Z)', re.S)
COUNTRY = re.compile(r"<div>([^<>]{2,60})</div>\s*<div>[^<>]*using the app</div>")

countries = {}
page = 1
while page <= 12:
    url = base if page == 1 else "%s?page=%d" % (base, page)
    html_ = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode("utf-8", "replace")
    blocks = REVIEW.findall(html_)
    if not blocks:
        break
    for rid, blk in blocks:
        m = COUNTRY.search(blk)
        if m:
            countries[rid] = m.group(1).strip()
    page += 1
    time.sleep(0.3)
print("countries read for %d listing reviews" % len(countries))

# ---- brand-strip marks ----------------------------------------------------
with io.open(BRANDS, encoding="utf-8") as fh:
    brands = json.load(fh)["brands"]
key = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
by_key = {key(b["name"]): b for b in brands}

matched_country = matched_logo = 0
out = []
for e in entries:
    r = {"quote": e["quote"], "name": e["name"], "date": e["date"], "rating": e["rating"]}
    c = countries.get(e["id"])
    if c:
        r["country"] = c
        matched_country += 1
    b = by_key.get(key(e["name"]))
    if b:
        r["logo"] = "assets/customers/" + b["file"]
        r["logoAlt"] = b["name"]
        matched_logo += 1
    out.append(r)

print("country attached to %d, logo attached to %d" % (matched_country, matched_logo))
missing = [e["name"] for e in entries if e["id"] not in countries]
if missing:
    print("no country for: %s" % ", ".join(missing))

doc = {
    "_note": "Source of truth for the reviews wall. Edit here, then run: python tools/build-reviews.py",
    "_source": "Shopify App Store CSV export for clickpost-order-edit-cancel; country looked up from the listing by review id",
    "_fields": {
        "quote": "required - review text, no surrounding quote marks (the card draws those)",
        "name": "required - store name",
        "date": "optional - review date, shown on the right of the card",
        "country": "optional - store country, shown under the date",
        "rating": "optional - stars, kept so the wall can be filtered",
        "logo": "optional - path under assets/ for the brand mark",
        "logoAlt": "optional - accessible name for the logo",
    },
    "reviews": out,
}
io.open(OUT, "w", encoding="utf-8", newline="\n").write(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
print("wrote reviews.json with %d reviews" % len(out))
