#!/usr/bin/env python3
"""Build the dotted world map SVG in assets/ from a blank basemap.

Usage:  python tools/build-world-dots.py path/to/robinson-basemap.png

Basemap: Wikimedia Commons "BlankMap-World.svg" (public domain), rendered
to PNG. That file is a Robinson projection and its canvas is exactly the
projection's bounding box, which is what lets pins be placed by formula
rather than by eye.

Equirectangular was the obvious choice - pixel position is just linear in
lon/lat - but it renders the world at 2:1 and stretches everything near the
poles sideways, which read as a squashed, over-wide map. Robinson is 1.97:1
and keeps the continents the shape people expect, at the cost of needing
the projection maths below.
"""

import io
import math
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "world-dots.svg")

STEP = 10            # sample grid, source px
R = 2.0              # dot radius, output units
UNIT = 5.4           # output units per grid step
DOT = "#CDD1D8"      # neutral grey; the pins carry the only colour
PIN = "#155FFF"

# Robinson's lookup table: length of the parallel (X) and its distance from
# the equator (Y), per 5 degrees of latitude.
RX = [1.0000, 0.9986, 0.9954, 0.9900, 0.9822, 0.9730, 0.9600, 0.9427, 0.9216,
      0.8962, 0.8679, 0.8350, 0.7986, 0.7597, 0.7186, 0.6732, 0.6213, 0.5722, 0.5322]
RY = [0.0000, 0.0620, 0.1240, 0.1860, 0.2480, 0.3100, 0.3720, 0.4340, 0.4958,
      0.5571, 0.6176, 0.6769, 0.7346, 0.7903, 0.8435, 0.8936, 0.9394, 0.9761, 1.0000]


def _interp(table, lat):
    a = abs(lat) / 5.0
    i = min(int(a), len(table) - 2)
    f = a - i
    return table[i] + (table[i + 1] - table[i]) * f


def project(lon, lat, w, h):
    """lon/lat -> pixel on a Robinson canvas that is exactly the projection box."""
    x = w / 2.0 + _interp(RX, lat) * (lon / 180.0) * (w / 2.0)
    y = h / 2.0 - math.copysign(_interp(RY, lat), lat) * (h / 2.0)
    return x, y


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "worldmap.png"
    im = Image.open(src).convert("LA")
    W, H = im.size
    px = im.load()

    # trim the poles: no customers up there, and Antarctica only adds width
    _, y_top = project(0, 84, W, H)
    _, y_bottom = project(0, -60, W, H)

    def is_land(sx, sy):
        lum, a = px[int(sx), int(sy)]
        return a > 40 and 60 < lum < 245

    dots = []
    sy = y_top
    while sy < y_bottom:
        sx = 0
        while sx < W:
            if is_land(sx, sy):
                # r is a geometry attribute - a parent group cannot hand it
                # down the way it does fill, so it goes on every circle
                dots.append('<circle cx="%.0f" cy="%.0f" r="%s"/>'
                            % (sx / STEP * UNIT, (sy - y_top) / STEP * UNIT, R))
            sx += STEP
        sy += STEP

    vw = W / STEP * UNIT
    vh = (y_bottom - y_top) / STEP * UNIT

    # every country this page can actually point to: the countries appearing
    # in reviews.json or brands.json, nothing beyond them
    PINS = [
        ("Vancouver", 49.28, -123.12), ("Toronto", 43.65, -79.38),
        ("Salt Lake City", 40.76, -111.89), ("New York", 40.71, -74.01),
        ("Berlin", 52.52, 13.40), ("Nicosia", 35.17, 33.36),
        ("Dubai", 25.20, 55.27), ("Delhi", 28.61, 77.21),
        ("Mumbai", 19.08, 72.88), ("Bengaluru", 12.97, 77.59),
    ]
    pins = []
    for _, lat, lon in PINS:
        sx, sy = project(lon, lat, W, H)
        cx, cy = sx / STEP * UNIT, (sy - y_top) / STEP * UNIT
        pins.append(
            '<g transform="translate(%.1f %.1f)">'
            '<path d="M0 2c-4.2 0-7.6 3.4-7.6 7.6 0 5.6 7.6 13.4 7.6 13.4s7.6-7.8 7.6-13.4'
            'C7.6 5.4 4.2 2 0 2z" fill="%s"/><circle cy="9.2" r="2.8" fill="#ffffff"/></g>'
            % (cx, cy - 23, PIN))

    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %.0f %.0f" width="%.0f" '
           'height="%.0f" fill="none" role="img" aria-label="World map with pins on the '
           'countries running ClickPost order editing: Canada, the United States, Germany, '
           'Cyprus, the UAE and India">' % (vw, vh, vw, vh)
           + '<g fill="%s">' % DOT + "".join(dots) + "</g>" + "".join(pins) + "</svg>")

    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(svg)
    print("dots %d  pins %d  viewBox %.0f x %.0f (%.2f:1)  %d bytes"
          % (len(dots), len(pins), vw, vh, vw / vh, len(svg)))


if __name__ == "__main__":
    main()
