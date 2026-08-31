#!/usr/bin/env python3
"""Find a logo for every review store that has none, and save it locally.

Usage:  python tools/fetch-review-logos.py [--only NAME]

For each store in reviews.json without a "logo", this tries a handful of
domains, checks the page actually belongs to that store, and takes the
best mark it can find. Colour is kept - these are the stores' own marks,
not silhouettes.

Verification matters more than coverage here. A guessed domain lands on
somebody else's site often enough that an unverified grab would put a
stranger's logo on the page under a customer's name, so a candidate is
only accepted when the store's name appears in the page's own title,
og:site_name or copyright line. Anything unverified is left as the text
wordmark it already is, and named in the report.

Mark preference, best first:
  1. an <img> in the markup whose src or alt says "logo" - usually the
     real wordmark, and usually transparent
  2. apple-touch-icon - square, at least 120px, no transparency
  3. favicon - last resort, often 32px and too small to set in a row
"""

import io
import json
import os
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "reviews.json")
OUT_DIR = os.path.join(ROOT, "assets", "reviews")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# Domains that a slug rule will not reach. Everything else is derived from
# the store name.
HINTS = {
    "bearhouseindia": ["bearhouse.in"],
    "V-Guard Industries Limited": ["vguard.in", "vguard.com"],
    "PairieTales": ["prairietales.in", "prairietales.com", "pairietales.com"],
    "Berry - Wellwithlife": ["wellwithlife.in", "wellwithlife.com"],
    "Wow - Wellwithlife": ["wellwithlife.in", "wellwithlife.com"],
    "Wellwith": ["wellwithlife.in", "wellwithlife.com"],
    "World of Asaya": ["asaya.in", "worldofasaya.com"],
    "Samoh by TATA": ["samoh.com", "samoh.in"],
    "Samoh International": ["samoh.com", "samoh.in"],
    "The Gareeb Store": ["thegareebstore.com", "gareebstore.com"],
    "Gully Labs": ["gullylabs.com"],
    "Starquik": ["starquik.com"],
    "Westside": ["westside.com"],
    "Burnt Toast": ["burnttoast.in", "burnttoastclothing.com"],
    "Italian Colony": ["italiancolony.in", "italiancolony.com"],
    "Shred Finger Boards": ["shredfingerboards.com"],
    "Recode Studios": ["recodestudios.com", "recode.in"],
    "Bacca Bucci": ["baccabucci.com"],
    "Tuco Kids": ["tucokids.com", "tuco.in"],
    "French Accent": ["frenchaccent.in", "frenchaccent.com"],
    "bearhouseindia": ["bearhouse.in", "bearhouseindia.com", "bearhouse.co.in"],
    "HoneyVeda": ["honeyveda.in", "honeyveda.co.in"],
    "MIRAGGIO": ["miraggio.in", "miraggiolife.com", "miraggio.co.in"],
    "Pinacolada": ["pinacolada.in", "pinacoladaindia.com", "shoppinacolada.com"],
    "Paradyes": ["paradyes.in", "paradyes.com"],
    "Gladful": ["gladful.com", "gladful.in"],
    "Tuco Kids": ["tucokids.com", "tucointelligentwear.com"],
    "sanskritagain": ["sanskritagain.com", "sanskritagain.in"],
}
TLDS = [".com", ".in", ".co.in", ".store"]


def slugs(name):
    base = re.sub(r"[^a-z0-9]+", "", name.lower())
    out = []
    for d in HINTS.get(name, []):
        out.append(d)
    for t in TLDS:
        out.append(base + t)
    # drop a leading "the"
    if base.startswith("the") and len(base) > 6:
        for t in TLDS:
            out.append(base[3:] + t)
    seen, uniq = set(), []
    for d in out:
        if d not in seen:
            seen.add(d)
            uniq.append(d)
    return uniq


def get(url, limit=400000):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=9) as r:
        return r.read(limit), r.geturl()


def verified(html, name):
    """Does this page actually belong to the store?"""
    key = re.sub(r"[^a-z0-9]+", "", name.lower())
    if len(key) < 4:
        return False
    fields = []
    for pat in (r"<title[^>]*>([^<]{0,200})</title>",
                r'property="og:site_name" content="([^"]{0,120})"',
                r'name="application-name" content="([^"]{0,120})"'):
        fields += re.findall(pat, html, re.I)
    # the copyright line is a reliable one on Shopify themes
    fields += re.findall(r"(?:©|&copy;|Copyright)[^<]{0,80}", html, re.I)
    hay = re.sub(r"[^a-z0-9]+", "", " ".join(fields).lower())
    if key in hay:
        return True
    # a two-word name may appear with only its first word in the title
    first = re.sub(r"[^a-z0-9]+", "", name.split()[0].lower())
    return len(first) >= 5 and first in hay


def absolute(src, base):
    if src.startswith("//"):
        return "https:" + src
    if src.startswith("http"):
        return src
    root = re.match(r"(https?://[^/]+)", base).group(1)
    return root + ("" if src.startswith("/") else "/") + src


def upscale(url):
    """A Shopify CDN asset asked for at favicon size is the same file as
    the store's logo asked for at any other size. Drop the sizing query
    and request something usable."""
    if "/cdn/shop/" not in url and "cdn.shopify.com" not in url:
        return url
    base = url.split("?")[0]
    m = re.search(r"[?&]v=(\d+)", url)
    q = "?width=600" + (("&v=" + m.group(1)) if m else "")
    return base + q


def candidates(html, base):
    out = []
    for m in re.finditer(r"<img[^>]+>", html[:250000], re.I):
        tag = m.group(0)
        if not re.search(r"logo", tag, re.I):
            continue
        src = re.search(r'(?:data-src|srcset|src)="([^"]+)"', tag)
        if not src:
            continue
        u = src.group(1).split()[0].split(",")[0]
        out.append(("logo", absolute(u, base)))
    for m in re.finditer(r"<link[^>]+>", html[:250000], re.I):
        tag = m.group(0)
        href = re.search(r'href="([^"]+)"', tag)
        if not href:
            continue
        rel = (re.search(r'rel="([^"]+)"', tag) or [None, ""])[1].lower()
        if "apple-touch-icon" in rel:
            out.append(("touch", absolute(href.group(1), base)))
        elif "icon" in rel:
            out.append(("icon", absolute(href.group(1), base)))
    out = [(k, upscale(u)) for k, u in out]
    rank = {"logo": 0, "touch": 1, "icon": 2}
    out.sort(key=lambda p: rank[p[0]])
    return out


def resolve(review):
    name = review["name"]
    for domain in slugs(name):
        for scheme in ("https://", "https://www."):
            try:
                raw, final = get(scheme + domain + "/")
            except Exception:
                continue
            html = raw.decode("utf-8", "replace")
            if not verified(html, name):
                continue
            for kind, url in candidates(html, final):
                try:
                    img, _ = get(url, 900000)
                except Exception:
                    continue
                if len(img) < 700:
                    continue
                ext = ".svg" if url.lower().split("?")[0].endswith(".svg") else ".png"
                slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
                path = os.path.join(OUT_DIR, slug + ext)
                with open(path, "wb") as f:
                    f.write(img)
                return name, domain, kind, os.path.relpath(path, ROOT).replace("\\", "/")
            return name, domain, "verified-but-no-mark", None
    return name, None, "unresolved", None


def main():
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]
    doc = json.load(io.open(DATA, encoding="utf-8"))
    todo = [r for r in doc["reviews"] if not r.get("logo")]
    if only:
        todo = [r for r in todo if r["name"] == only]
    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(resolve, todo))

    found = {}
    for name, domain, kind, path in results:
        print("%-24s %-26s %-22s %s" % (name[:24], domain or "-", kind, path or ""))
        if path:
            found[name] = path
    print("\n%d of %d resolved" % (len(found), len(todo)))
    io.open(os.path.join(OUT_DIR, "_found.json"), "w", encoding="utf-8").write(
        json.dumps(found, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
