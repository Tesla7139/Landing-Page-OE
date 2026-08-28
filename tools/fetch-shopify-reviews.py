#!/usr/bin/env python3
"""Scrape every review from the Shopify App Store listing into reviews.json.

Usage:  python tools/fetch-shopify-reviews.py [--dry-run]

Defaults to the CP: Order Editing & Upsell listing. Note that
/order-editing is a DIFFERENT app (OrderEditing.com, a competitor) -
the handle matters.

The listing pages are server-rendered, so the reviews come straight out of
the HTML - no API key, no headless browser. Ten per page; it walks pages
until one comes back empty.

Existing entries keep any hand-added fields (logo, logoAlt, avatar) - they
are matched on store name, so a store that appears twice keeps whichever
extras were already attached to it.
"""

import argparse
import html
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "reviews.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) landing-page-review-sync"

BLOCK = re.compile(r'data-review-content-id="(\d+)"(.*?)(?=data-review-content-id="|\Z)', re.S)
RATING = re.compile(r'aria-label="(\d) out of 5 stars"')
DATE = re.compile(r'tw-text-fg-tertiary">\s*([A-Z][a-z]+ \d{1,2}, \d{4})\s*<')
BODY = re.compile(r'<p class="tw-break-words">(.*?)</p>', re.S)
NAME = re.compile(r'<span class="tw-overflow-hidden[^"]*"\s*title="([^"]*)"')
TAGS = re.compile(r"<[^>]+>")


def text(fragment):
    fragment = re.sub(r"<br\s*/?>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(TAGS.sub("", fragment))).strip()


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def parse(page_html):
    out = []
    for rid, blk in BLOCK.findall(page_html):
        body = BODY.search(blk)
        name = NAME.search(blk)
        if not body or not name:
            continue
        if not text(body.group(1)):
            continue  # a star rating with no words - nothing to put on a card
        rating = RATING.search(blk)
        date = DATE.search(blk)
        out.append({
            "id": rid,
            "quote": text(body.group(1)),
            "name": html.unescape(name.group(1)).strip(),
            "date": date.group(1) if date else "",
            "rating": int(rating.group(1)) if rating else None,
        })
    return out


MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def sort_key(r):
    """Newest first. Anything unparseable sorts last rather than blowing up."""
    m = re.match(r"([A-Z][a-z]+) (\d{1,2}), (\d{4})", r.get("date", "") or "")
    if not m or m.group(1) not in MONTHS:
        return (0, 0, 0)
    return (int(m.group(3)), MONTHS.index(m.group(1)) + 1, int(m.group(2)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--handle", default="clickpost-order-edit-cancel", help="app handle on apps.shopify.com")
    ap.add_argument("--max-pages", type=int, default=60)
    ap.add_argument("--dry-run", action="store_true", help="report what was found, write nothing")
    ap.add_argument("--replace", action="store_true",
                    help="drop entries whose store is no longer on the listing")
    args = ap.parse_args()

    base = "https://apps.shopify.com/%s/reviews" % args.handle
    scraped, seen = [], set()

    for page in range(1, args.max_pages + 1):
        url = base if page == 1 else "%s?page=%d" % (base, page)
        try:
            found = parse(fetch(url))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                break
            sys.exit("page %d: HTTP %s" % (page, e.code))
        if not found:
            break
        fresh = [r for r in found if r["id"] not in seen]
        seen.update(r["id"] for r in fresh)
        scraped += fresh
        print("  page %-2d  +%d  (%d total)" % (page, len(fresh), len(scraped)))
        if not fresh:
            break
        time.sleep(0.4)

    if not scraped:
        sys.exit("no reviews parsed — the listing markup probably changed")

    with io.open(DATA, encoding="utf-8") as fh:
        doc = json.load(fh)

    # carry over per-store extras that were added by hand
    extras = {}
    for r in doc.get("reviews", []):
        keep = {k: v for k, v in r.items() if k in ("logo", "logoAlt", "avatar", "initials", "role")}
        if keep:
            extras[r["name"]] = keep

    scraped_names = {r["name"] for r in scraped}
    stale = [r for r in doc.get("reviews", []) if r["name"] not in scraped_names]

    merged = []
    for r in scraped:
        entry = {"quote": r["quote"], "name": r["name"], "date": r["date"]}
        # kept so the wall can be filtered by rating - the listing is not
        # all five stars, and a landing page may not want the low ones
        if r["rating"] is not None:
            entry["rating"] = r["rating"]
        entry.update(extras.get(r["name"], {}))
        merged.append(entry)

    if stale and not args.replace:
        # a store can rename itself or pull its review; keep what we already
        # had rather than silently dropping testimonials off the page
        merged += stale
        print("")
        print("kept %d review(s) no longer on the listing:" % len(stale))
        for r in stale:
            print("  %s (%s)" % (r["name"], r.get("date", "?")))
    elif stale:
        print("")
        print("dropped %d review(s) no longer on the listing: %s"
              % (len(stale), ", ".join(r["name"] for r in stale)))

    merged.sort(key=sort_key, reverse=True)

    stars = {}
    for r in scraped:
        stars[r["rating"]] = stars.get(r["rating"], 0) + 1
    print("\n%d reviews, %d distinct stores" % (len(merged), len({r["name"] for r in merged})))
    print("ratings: %s" % ", ".join("%s-star: %d" % (k, v) for k, v in sorted(stars.items(), reverse=True)))

    if args.dry_run:
        print("\n--dry-run: reviews.json untouched")
        return

    doc["reviews"] = merged
    doc["_source"] = "Scraped from %s — refresh with tools/fetch-shopify-reviews.py" % base
    with io.open(DATA, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    print("wrote reviews.json — now run: python tools/build-reviews.py")


if __name__ == "__main__":
    main()
