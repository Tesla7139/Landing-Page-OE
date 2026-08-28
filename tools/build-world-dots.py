"""Build a dotted world map SVG from a blank equirectangular basemap.

Basemap: Wikimedia Commons "BlankMap-Equirectangular.svg" (public domain),
1920x960 and exactly 2:1, so pixel <-> lon/lat is linear:
    x = (lon + 180) / 360 * W
    y = (90  - lat) / 180 * H

which is what lets the pins land on real cities rather than being nudged
into place by eye.
"""
from PIL import Image
import io

SRC = "eqmap.png"
OUT = r"c:\Users\sarth\Desktop\Landing Page OE\assets\world-dots.svg"

STEP = 15          # sample grid, source px
R = 2.1            # dot radius in output units
LAT_TOP, LAT_BOTTOM = 80.0, -56.0   # trim the poles: no customers, and
                                    # Antarctica just weighs the shape down

im = Image.open(SRC).convert("LA")
W, H = im.size
px = im.load()


def to_xy(lon, lat):
    return ((lon + 180.0) / 360.0 * W, (90.0 - lat) / 180.0 * H)


x0, y0 = to_xy(-180, LAT_TOP)
x1, y1 = to_xy(180, LAT_BOTTOM)
vw, vh = (x1 - x0) / STEP * 6.0, (y1 - y0) / STEP * 6.0   # 6 units per dot


def is_land(sx, sy):
    lum, a = px[int(sx), int(sy)]
    return a > 40 and lum > 40


dots = []
sy = y0
while sy < y1:
    sx = x0
    while sx < x1:
        if is_land(sx, sy):
            cx = (sx - x0) / STEP * 6.0
            cy = (sy - y0) / STEP * 6.0
            # r has to sit on the element: it is a geometry attribute, so a
            # group cannot hand it down the way it does fill
            dots.append('<circle cx="%.0f" cy="%.0f" r="%s"/>' % (cx, cy, R))
        sx += STEP
    sy += STEP

# real coordinates of the places this page can actually claim: every country
# that appears in reviews.json or brands.json
PINS = [
    ("Vancouver", 49.28, -123.12),
    ("Toronto", 43.65, -79.38),
    ("Salt Lake City", 40.76, -111.89),
    ("New York", 40.71, -74.01),
    ("Berlin", 52.52, 13.40),
    ("Nicosia", 35.17, 33.36),
    ("Dubai", 25.20, 55.27),
    ("Delhi", 28.61, 77.21),
    ("Mumbai", 19.08, 72.88),
    ("Bengaluru", 12.97, 77.59),
]

pins = []
for name, lat, lon in PINS:
    sx, sy = to_xy(lon, lat)
    cx = (sx - x0) / STEP * 6.0
    cy = (sy - y0) / STEP * 6.0
    pins.append(
        '<g transform="translate(%.1f %.1f)">'
        '<path d="M0 2c-4.4 0-8 3.5-8 7.9 0 5.9 8 14.1 8 14.1s8-8.2 8-14.1C8 5.5 4.4 2 0 2z" '
        'fill="#155FFF"/><circle cy="9.6" r="3" fill="#ffffff"/></g>' % (cx, cy - 24)
    )

svg = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %.0f %.0f" width="%.0f" height="%.0f" '
    'fill="none" role="img" aria-label="World map with pins on the countries using ClickPost order editing: '
    'Canada, the United States, Germany, Cyprus, the UAE and India">' % (vw, vh, vw, vh)
    + '<g fill="#C9CEDC">' + "".join(dots) + "</g>"
    + "".join(pins)
    + "</svg>"
)
io.open(OUT, "w", encoding="utf-8", newline="\n").write(svg)
print("dots: %d   pins: %d   viewBox: %.0f x %.0f   bytes: %d"
      % (len(dots), len(pins), vw, vh, len(svg)))
