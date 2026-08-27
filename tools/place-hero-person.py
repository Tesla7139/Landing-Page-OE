"""Insert (or re-position) the hero person layer in the phone SVG.

Sits between the phone group and the floating stat cards, so she overlaps
the device but the 40% / 5% cards still land on top of her - same stacking
as the reference composite.

usage: place-hero-person.py assets/hero-person.webp 23 260 377 640

The device is loaded as <img src=...svg>, and browsers refuse external
image refs inside an SVG loaded that way, so the photo is inlined as a
data URI rather than referenced by path.
"""
import base64, io, re, sys

import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG = os.path.join(ROOT, "assets", "order-editing-phone.svg")
png, x, y, w, h = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]

b64 = base64.b64encode(open(png, "rb").read()).decode("ascii")
layer = (
    '\n  <!-- ============ hero person ============ -->\n'
    '  <image id="oePerson" x="{x}" y="{y}" width="{w}" height="{h}" '
    'preserveAspectRatio="xMidYMax meet" href="data:image/png;base64,{b64}"/>\n'
).format(x=x, y=y, w=w, h=h, b64=b64, mime="webp" if png.lower().endswith(".webp") else "png")

s = io.open(SVG, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in s else "\n"

# drop any previous layer first so this is idempotent
s = re.sub(r'\s*<!-- =+ hero person =+ -->\s*<image id="oePerson".*?/>', "", s, flags=re.S)

anchor = "  <!-- ============ floating stat cards over the device ============ -->"
i = s.index(anchor)
s = s[:i] + layer.replace("\n", NL).lstrip("\r\n") + s[i:]

io.open(SVG, "w", encoding="utf-8", newline="").write(s)
print("person at", x, y, w, h, "-", len(b64), "b64 chars")
