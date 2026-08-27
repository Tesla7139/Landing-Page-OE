"""Cut the woman out of the pasted composite.

Flood-fills the page background inward from the window edge, so anything the
fill can't reach counts as her - that keeps interior whites (her tank top)
instead of punching holes through them. The two stat cards and the phone
frame are then removed by geometry, and the largest blob wins.
"""
from PIL import Image, ImageFilter
from collections import deque

SRC = "hero-source.png"   # flat composite the photo was lifted from
im = Image.open(SRC).convert("RGB")
W, H = im.size
px = im.load()

X0, X1, Y0, Y1 = 0, 340, 95, H          # her side of the composite
CARDS = [(0, 20, 178, 152), (0, 262, 152, 416)]   # drawn again by the SVG
PHONE_X = 246                            # left edge of the device frame
HAND = (452, 558)                        # rows where her hands cross onto it
HAND_X1 = 323


def isbg(p):
    r, g, b = p
    mn, mx = min(p), max(p)
    if mn > 232 and mx - mn < 14:                     # page / card white
        return True
    if mn > 205 and b >= r and b - r < 40 and g <= b: # pale blue blob
        return True
    return False


bg = bytearray(W * H)
for y in range(Y0, Y1):
    for x in range(X0, X1):
        if isbg(px[x, y]):
            bg[y * W + x] = 1

# flood the background in from the window border
outside = bytearray(W * H)
q = deque()
for y in range(Y0, Y1):
    for x in (X0, X1 - 1):
        i = y * W + x
        if bg[i] and not outside[i]:
            outside[i] = 1; q.append(i)
for x in range(X0, X1):
    for y in (Y0, Y1 - 1):
        i = y * W + x
        if bg[i] and not outside[i]:
            outside[i] = 1; q.append(i)
while q:
    j = q.popleft(); jy, jx = divmod(j, W)
    for ny, nx in ((jy-1,jx),(jy+1,jx),(jy,jx-1),(jy,jx+1)):
        if Y0 <= ny < Y1 and X0 <= nx < X1:
            k = ny * W + nx
            if bg[k] and not outside[k]:
                outside[k] = 1; q.append(k)

mask = bytearray(W * H)
for y in range(Y0, Y1):
    for x in range(X0, X1):
        i = y * W + x
        if not outside[i]:
            mask[i] = 1

for cx0, cy0, cx1, cy1 in CARDS:
    for y in range(cy0, cy1 + 1):
        for x in range(cx0, cx1 + 1):
            mask[y * W + x] = 0

for y in range(Y0, Y1):
    lim = HAND_X1 if HAND[0] <= y <= HAND[1] else PHONE_X
    for x in range(lim, X1):
        mask[y * W + x] = 0

seen = bytearray(W * H); best, bestn = None, 0
for sy in range(Y0, Y1):
    for sx in range(X0, X1):
        i = sy * W + sx
        if not mask[i] or seen[i]:
            continue
        q = deque([i]); seen[i] = 1; comp = [i]
        while q:
            j = q.popleft(); jy, jx = divmod(j, W)
            for ny, nx in ((jy-1,jx),(jy+1,jx),(jy,jx-1),(jy,jx+1)):
                if Y0 <= ny < Y1 and X0 <= nx < X1:
                    k = ny * W + nx
                    if mask[k] and not seen[k]:
                        seen[k] = 1; q.append(k); comp.append(k)
        if len(comp) > bestn:
            best, bestn = comp, len(comp)
print("largest blob:", bestn, "px")

alpha = Image.new("L", (W, H), 0)
apx = alpha.load()
xs, ys = [], []
for i in best:
    y, x = divmod(i, W)
    apx[x, y] = 255; xs.append(x); ys.append(y)
alpha = alpha.filter(ImageFilter.GaussianBlur(0.6))   # soften the 1px stair-step

out = im.convert("RGBA")
out.putalpha(alpha)
bx0, bx1, by0, by1 = min(xs), max(xs), min(ys), max(ys)
print("bbox", bx0, by0, bx1, by1, "->", bx1-bx0+1, "x", by1-by0+1)
cut = out.crop((bx0, by0, bx1 + 1, by1 + 1))
cut.save("person-cut.png")
prev = Image.new("RGB", cut.size, (120, 130, 145))
prev.paste(cut, (0, 0), cut)
prev.save("person-cut-preview.png")
