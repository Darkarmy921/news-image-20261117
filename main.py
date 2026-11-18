#!/usr/bin/env python3
"""news-image-20261117 v2: THE WORLD IN FOCUS - 17 November 2026.

A Python 3.13 standard-library-only program. It draws a one-page newspaper
front page (1024 x 1024) summing up the world news of Tuesday 17 November
2026 and writes it to $MAKEFUN_OUTPUT_DIR/entry.png (or /output/entry.png).
No network, no time, no randomness: two runs write byte-identical files.

The day's five stories (see NEWS.md for sources):
  1. LEAD - a Ukrainian strike drops the road arch of the 19-km Kerch
     Bridge into the sea; traffic halted, the rail arch still stands.
  2. U.S. and Iran trade fire in the Gulf: Iranian drones at a U.S. radar
     in Bahrain are intercepted, no injuries; U.S. jets answer on Qeshm
     Island. Tankers were also hit near Hormuz; Iran's mine claims are
     unverified.
  3. Trump lands in Manila for the first Quad leaders' summit in two
     years; an AI accelerator is launched and Thailand is to scrap tariffs
     on U.S. goods.
  4. Nvidia reports $115.8B revenue, up 103%, in its first results since
     Jensen Huang's exit; Q4 guidance $130B.
  5. A software bug (not a hack) slows Chase banking and Zelle; about
     4,800 reports at peak.

Everything is drawn procedurally: a small raster canvas, a 5x7 bitmap font
defined below, flat-colour scenes (the broken bridge, the Gulf tanker,
the four Quad flags, a chip, a bank), and a PNG encoder built on zlib.

Canvas note: the mission brief asked for 1536x1024, but the competition
gate caps the image at 1024x1024, so this build is 1024x1024 - the
largest square the gate allows.
"""

import binascii
import os
import struct
import zlib

# ------------------------------------------------------------------ size

W = 1024
H = 1024

# ---------------------------------------------------------------- palette

PAPER = (247, 243, 234)      # warm off-white page
PANEL = (253, 251, 246)      # panel fill, near-white
INK = (22, 21, 19)           # near-black text / frames
RED = (168, 30, 35)          # kickers, rules, stat strips
NAVY = (29, 42, 74)          # masthead and footer bands
ROSE = (224, 163, 166)       # theme line on the navy band
MIST = (201, 206, 218)       # secondary text on the navy band
SKY = (191, 217, 232)        # lead illustration sky
SEA = (46, 110, 166)         # lead illustration sea
SAND = (227, 217, 190)       # distant shore in the lead scene
DECK = (43, 43, 43)          # bridge deck
STEEL = (84, 78, 70)         # bridge pillars and fallen steel
SMOKE = (138, 138, 138)      # smoke puffs
SMOKE_D = (90, 88, 84)       # dark smoke core
GREY = (107, 103, 94)        # muted grey (source line only)
WHITE = (255, 255, 255)
SAFFRON = (232, 114, 42)     # India flag top band
LEAF = (46, 125, 50)         # India flag bottom band
GOLD = (232, 194, 0)         # small accents


# ------------------------------------------------------------------ raster


class Sheet:
    """A plain RGB raster with a few flat drawing primitives."""

    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)
        self.rect(0, 0, w, h, bg)

    def _at(self, x, y):
        return (y * self.w + x) * 3

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = self._at(x, y)
            self.px[i] = c[0]
            self.px[i + 1] = c[1]
            self.px[i + 2] = c[2]

    def rect(self, x, y, w, h, c):
        x0 = max(x, 0)
        y0 = max(y, 0)
        x1 = min(x + w, self.w)
        y1 = min(y + h, self.h)
        for yy in range(y0, y1):
            base = self._at(x0, yy)
            for xx in range(x0, x1):
                i = base + (xx - x0) * 3
                self.px[i] = c[0]
                self.px[i + 1] = c[1]
                self.px[i + 2] = c[2]

    def frame(self, x, y, w, h, c, t=2):
        self.rect(x, y, w, t, c)
        self.rect(x, y + h - t, w, t, c)
        self.rect(x, y, t, h, c)
        self.rect(x + w - t, y, t, h, c)

    def hline(self, x, y, w, c, t=1):
        self.rect(x, y, w, t, c)

    def vline(self, x, y, h, c, t=1):
        self.rect(x, y, t, h, c)

    def seg(self, x0, y0, x1, y1, c, t=1):
        """Bresenham segment; thickness t draws a t x t block per step."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x, y = x0, y0
        half = t // 2
        while True:
            self.rect(x - half, y - half, t, t, c)
            if x == x1 and y == y1:
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy

    def disc(self, cx, cy, r, c):
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                if (xx - cx) * (xx - cx) + (yy - cy) * (yy - cy) <= r * r:
                    self.put(xx, yy, c)

    def poly(self, pts, c):
        """Scanline fill of a simple polygon given as [(x, y), ...]."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        for yy in range(min(ys), max(ys) + 1):
            nodes = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= yy < y1) or (y1 <= yy < y0):
                    nodes.append(x0 + (yy - y0) * (x1 - x0) / (y1 - y0))
            nodes.sort()
            for k in range(0, len(nodes) - 1, 2):
                xa = int(nodes[k] + 0.5)
                xb = int(nodes[k + 1] + 0.5)
                self.rect(xa, yy, xb - xa + 1, 1, c)

    def tri(self, x0, y0, x1, y1, x2, y2, c):
        self.poly([(x0, y0), (x1, y1), (x2, y2)], c)


# -------------------------------------------------------------------- font
# One 5x7 bitmap family, drawn at integer scales. '#' is ink, '.' empty.
# Uppercase, lowercase, digits and the punctuation the page needs.

FONT = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "a": (".....", ".....", ".###.", "....#", ".####", "#...#", ".####"),
    "b": ("#....", "#....", "####.", "#...#", "#...#", "#...#", "####."),
    "c": (".....", ".....", ".####", "#....", "#....", "#....", ".####"),
    "d": ("....#", "....#", ".####", "#...#", "#...#", "#...#", ".####"),
    "e": (".....", ".....", ".###.", "#...#", "#####", "#....", ".###."),
    "f": ("..##.", ".#...", ".#...", "####.", ".#...", ".#...", ".#..."),
    "g": (".....", ".####", "#...#", "#...#", ".####", "....#", ".###."),
    "h": ("#....", "#....", "####.", "#...#", "#...#", "#...#", "#...#"),
    "i": (".....", "..#..", ".....", ".##..", "..#..", "..#..", ".###."),
    "j": ("...#.", ".....", "..##.", "...#.", "...#.", "#..#.", ".##.."),
    "k": ("#....", "#....", "#..#.", "#.#..", "##...", "#.#..", "#..#."),
    "l": (".##..", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "m": (".....", ".....", "##.#.", "#.#.#", "#.#.#", "#.#.#", "#.#.#"),
    "n": (".....", ".....", "####.", "#...#", "#...#", "#...#", "#...#"),
    "o": (".....", ".....", ".###.", "#...#", "#...#", "#...#", ".###."),
    "p": (".....", "####.", "#...#", "#...#", "####.", "#....", "#...."),
    "q": (".....", ".####", "#...#", "#...#", ".####", "....#", "...#."),
    "r": (".....", ".....", "#.##.", "##..#", "#....", "#....", "#...."),
    "s": (".....", ".....", ".####", "#....", ".###.", "....#", "####."),
    "t": (".#...", ".#...", "####.", ".#...", ".#...", ".#...", "..##."),
    "u": (".....", ".....", "#...#", "#...#", "#...#", "#...#", ".###."),
    "v": (".....", ".....", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "w": (".....", ".....", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    "x": (".....", ".....", "#...#", ".#.#.", "..#..", ".#.#.", "#...#"),
    "y": (".....", "#...#", "#...#", "#...#", ".####", "....#", ".###."),
    "z": (".....", ".....", "#####", "...#.", "..#..", ".#...", "#####"),
    "0": (".###.", "#..##", "#.#.#", "##..#", "#...#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", "..#..", "..#..", "..#.."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    ".": (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
    ",": (".....", ".....", ".....", ".....", ".##..", ".##..", ".#..."),
    ":": (".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."),
    ";": (".....", ".##..", ".##..", ".....", ".##..", ".##..", ".#..."),
    "'": ("..#..", "..#..", ".#...", ".....", ".....", ".....", "....."),
    "!": ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
    "?": (".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."),
    "-": (".....", ".....", ".....", "#####", ".....", ".....", "....."),
    "\u2014": (".....", ".....", ".....", "#####", "#####", ".....", "....."),
    "\u00b7": (".....", ".....", ".....", ".##..", ".##..", ".....", "....."),
    "$": ("..#..", ".####", "#.#..", ".###.", "..#.#", "####.", "..#.."),
    "%": ("##..#", "##.#.", "...#.", "..#..", ".#...", "#.#.#", "#..##"),
    "~": (".....", ".....", ".#.#.", "#.#.#", ".....", ".....", "....."),
    "(": ("...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."),
    ")": (".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."),
    "/": ("....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."),
    "+": (".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."),
    "=": (".....", ".....", "#####", ".....", "#####", ".....", "....."),
    '"': (".#.#.", ".#.#.", ".....", ".....", ".....", ".....", "....."),
    "&": (".##..", "#..#.", "#..#.", ".#...", "#.#.#", "#..#.", ".##.#"),
    "#": ("#.#.#", "#.#.#", "#####", "#.#.#", "#####", "#.#.#", "#.#.#"),
    "*": (".....", ".#.#.", "..#..", "#####", "..#..", ".#.#.", "....."),
}

UNKNOWN = ("#####", "#...#", "#.###", "#.#.#", "#####", "#...#", "#####")


def text_w(s, scale):
    """Pixel width of s at scale (one scale-wide gap between glyphs)."""
    if not s:
        return 0
    return len(s) * 6 * scale - scale


def glyph(cv, x, y, ch, scale, color):
    rows = FONT.get(ch, UNKNOWN)
    for ry in range(7):
        row = rows[ry]
        for rx in range(5):
            if row[rx] == "#":
                cv.rect(x + rx * scale, y + ry * scale, scale, scale, color)


def text(cv, x, y, s, scale, color, align="left", width=None):
    """Draw one line. align centre/right need the width of the field."""
    w = text_w(s, scale)
    if align == "center" and width is not None:
        x = x + (width - w) // 2
    elif align == "right" and width is not None:
        x = x + width - w
    cx = x
    for ch in s:
        glyph(cv, cx, y, ch, scale, color)
        cx += 6 * scale
    return w


def wrap(s, scale, max_w):
    """Greedy word wrap; returns a list of lines that fit max_w."""
    lines = []
    for chunk in s.split("\n"):
        words = chunk.split(" ")
        cur = ""
        for word in words:
            trial = word if not cur else cur + " " + word
            if text_w(trial, scale) <= max_w:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
    return lines


def para(cv, x, y, s, scale, color, max_w, leading=None):
    """Draw a wrapped paragraph; returns the y just below the last line."""
    if leading is None:
        leading = int(7 * scale * 1.35)
    lines = wrap(s, scale, max_w)
    for i, line in enumerate(lines):
        text(cv, x, y + i * leading, line, scale, color)
    if lines:
        return y + (len(lines) - 1) * leading + 7 * scale
    return y


# --------------------------------------------------------------------- png


def png_bytes(cv):
    """Encode the sheet as a PNG (truecolour, filter 0, zlib level 9)."""

    def chunk(kind, data):
        out = struct.pack(">I", len(data)) + kind + data
        out += struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    raw = bytearray()
    for yy in range(cv.h):
        raw.append(0)
        raw += cv.px[yy * cv.w * 3:(yy + 1) * cv.w * 3]
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


# ------------------------------------------------------------------ scenes


def lead_scene(cv, x0, y0, w, h):
    """The Kerch Bridge: sky, shore, sea, a deck with a gap in the middle,
    the standing road arch on the left, its broken stub on the right, the
    fallen arch in the water, and smoke over the gap."""
    sky_h = 172
    sea_y = y0 + 178
    cv.rect(x0, y0, w, sky_h, SKY)
    cv.rect(x0, y0 + 164, w, 14, SAND)          # distant shore
    cv.rect(x0, sea_y, w, y0 + h - sea_y, SEA)  # the strait

    # white wave dashes on the sea
    for wx, wy, wl in (
        (x0 + 30, sea_y + 30, 34), (x0 + 150, sea_y + 52, 26),
        (x0 + 330, sea_y + 26, 40), (x0 + 420, sea_y + 58, 30),
        (x0 + 90, sea_y + 92, 30), (x0 + 260, sea_y + 100, 36),
        (x0 + 390, sea_y + 118, 26), (x0 + 40, sea_y + 118, 22),
    ):
        cv.hline(wx, wy, wl, WHITE, 3)

    deck_y = y0 + 130
    gap_l = x0 + 196
    gap_r = x0 + 308
    # deck, left and right of the gap
    cv.rect(x0, deck_y, gap_l - x0, 16, DECK)
    cv.rect(gap_r, deck_y, x0 + w - gap_r, 16, DECK)
    # lane dashes on the deck
    for dx in range(x0 + 14, x0 + w - 20, 34):
        if dx + 16 < gap_l or dx > gap_r:
            cv.hline(dx, deck_y + 7, 16, WHITE, 2)
    # pillars down into the water
    for px in (x0 + 44, x0 + 140, x0 + 356, x0 + 452):
        cv.rect(px, deck_y + 16, 10, 48, STEEL)

    # standing road arch, left of the gap: a parabola of thick segments
    prev = None
    for step in range(0, 33):
        ax = x0 + 24 + step * 5
        t = step / 32.0
        ay = deck_y - int(72 * (1 - (2 * t - 1) ** 2))
        if prev is not None:
            cv.seg(prev[0], prev[1], ax, ay, INK, 6)
        prev = (ax, ay)
    # broken stub of the arch on the right: rises, then stops mid-air
    prev = None
    for step in range(0, 9):
        ax = gap_r + 8 + step * 5
        t = step / 16.0
        ay = deck_y - int(72 * (1 - (2 * t - 1) ** 2))
        if prev is not None:
            cv.seg(prev[0], prev[1], ax, ay, INK, 6)
        prev = (ax, ay)

    # smoke over the gap
    for cx, cy, r, c in (
        (x0 + 232, y0 + 96, 15, SMOKE),
        (x0 + 258, y0 + 74, 19, SMOKE),
        (x0 + 286, y0 + 98, 12, SMOKE),
        (x0 + 258, y0 + 78, 9, SMOKE_D),
        (x0 + 234, y0 + 98, 6, SMOKE_D),
    ):
        cv.disc(cx, cy, r, c)

    # the fallen road arch: a sagging arc of steel, half under water,
    # with white foam where it went in
    prev = None
    for step in range(0, 13):
        ax = x0 + 206 + step * 8
        t = step / 12.0
        ay = sea_y + 30 + int(34 * (1 - (2 * t - 1) ** 2))
        if prev is not None:
            cv.seg(prev[0], prev[1], ax, ay, INK, 6)
        prev = (ax, ay)
    for fx, fy, fl in (
        (x0 + 206, sea_y + 62, 22), (x0 + 238, sea_y + 78, 30),
        (x0 + 282, sea_y + 84, 24), (x0 + 296, sea_y + 60, 16),
    ):
        cv.hline(fx, fy, fl, WHITE, 3)


def gulf_strip(cv, x0, y0, w, h):
    """Gulf strip: a tanker on the sea, two jets overhead, smoke aft."""
    cv.rect(x0, y0, w, h, (220, 233, 242))
    sea_y = y0 + h - 22
    cv.rect(x0, sea_y, w, 22, SEA)
    cv.hline(x0 + 20, sea_y + 8, 30, WHITE, 2)
    cv.hline(x0 + 330, sea_y + 12, 36, WHITE, 2)
    # tanker: dark hull, pale superstructure, red funnel
    cv.rect(x0 + 56, sea_y - 14, 190, 16, NAVY)
    cv.rect(x0 + 196, sea_y - 30, 42, 16, WHITE)
    cv.rect(x0 + 150, sea_y - 24, 14, 10, RED)
    cv.rect(x0 + 66, sea_y - 20, 8, 6, WHITE)
    # smoke puff aft of the tanker, inside the strip
    cv.disc(x0 + 232, y0 + 12, 7, SMOKE)
    cv.disc(x0 + 240, y0 + 7, 4, SMOKE_D)
    # two jets with contrails
    for jx, jy in ((x0 + 320, y0 + 12), (x0 + 372, y0 + 6)):
        cv.hline(jx - 44, jy + 3, 34, WHITE, 2)
        cv.tri(jx, jy, jx + 22, jy + 4, jx, jy + 8, INK)
        cv.tri(jx + 6, jy + 1, jx + 12, jy + 4, jx + 6, jy + 7, INK)


def quad_flags(cv, x0, y0, w, h):
    """Four Quad flags, each labelled underneath: USA, JPN, IND, AUS.
    Drawn from the simplest correct geometry for each flag."""
    fw, fh = 104, 32
    gap = 8
    labels = ("USA", "JPN", "IND", "AUS")
    for i, label in enumerate(labels):
        fx = x0 + i * (fw + gap)
        fy = y0
        if label == "USA":
            cv.rect(fx, fy, fw, fh, WHITE)
            for s in range(7):  # seven red stripes
                cv.rect(fx, fy + s * 5, fw, 2, RED)
            cv.rect(fx, fy, 42, 17, NAVY)  # canton
            for gy in range(3):
                for gx in range(4):
                    cv.disc(fx + 6 + gx * 10, fy + 4 + gy * 5, 1, WHITE)
        elif label == "JPN":
            cv.rect(fx, fy, fw, fh, WHITE)
            cv.disc(fx + fw // 2, fy + fh // 2, 10, RED)
        elif label == "IND":
            cv.rect(fx, fy, fw, 11, SAFFRON)
            cv.rect(fx, fy + 11, fw, 10, WHITE)
            cv.rect(fx, fy + 21, fw, 11, LEAF)
            cv.disc(fx + fw // 2, fy + fh // 2, 6, NAVY)
            cv.disc(fx + fw // 2, fy + fh // 2, 2, WHITE)
        else:  # AUS
            cv.rect(fx, fy, fw, fh, NAVY)
            # simplified Union Jack canton: white saltire, red cross
            cv.rect(fx, fy, 52, 16, WHITE)
            cv.seg(fx, fy, fx + 52, fy + 16, RED, 2)
            cv.seg(fx + 52, fy, fx, fy + 16, RED, 2)
            cv.hline(fx, fy + 6, 52, RED, 4)
            cv.vline(fx + 24, fy, 16, RED, 4)
            # Southern Cross + big star, as white dots
            for sx, sy in ((72, 8), (86, 18), (96, 8), (80, 26), (66, 24)):
                cv.disc(fx + sx, fy + sy, 2, WHITE)
        cv.frame(fx, fy, fw, fh, INK, 1)
        text(cv, fx, fy + fh + 4, label, 2, INK, align="center", width=fw)


def chip_icon(cv, x, y, s):
    """A small microchip: navy body, pins on four sides, red die."""
    body = s
    cv.rect(x - 4, y + body // 3, 4, body // 3, INK)
    cv.rect(x + body, y + body // 3, 4, body // 3, INK)
    cv.rect(x + body // 3, y - 4, body // 3, 4, INK)
    cv.rect(x + body // 3, y + body, body // 3, 4, INK)
    cv.rect(x, y, body, body, NAVY)
    cv.rect(x + body // 4, y + body // 4, body // 2, body // 2, RED)
    cv.rect(x + body // 4 + 3, y + body // 4 + 3, 4, 4, WHITE)


def bank_icon(cv, x, y, s):
    """A small bank: pediment, three columns, stepped base."""
    cv.tri(x, y + s // 3, x + s // 2, y, x + s, y + s // 3, INK)
    cv.rect(x + 2, y + s // 3 + 3, s - 4, 3, INK)
    for cx in (x + 4, x + s // 2 - 3, x + s - 10):
        cv.rect(cx, y + s // 3 + 8, 6, s // 2, INK)
    cv.rect(x, y + s // 3 + 8 + s // 2 + 3, s, 4, INK)
    cv.rect(x - 3, y + s // 3 + 8 + s // 2 + 9, s + 6, 4, RED)


# -------------------------------------------------------------------- page


def draw_headline(cv, x, y, s, scale, color, max_w, leading):
    """Wrapped all-caps headline; returns the y below the last line."""
    lines = wrap(s, scale, max_w)
    for i, line in enumerate(lines):
        text(cv, x, y + i * leading, line, scale, color)
    if lines:
        return y + (len(lines) - 1) * leading + 7 * scale
    return y


def build():
    cv = Sheet(W, H, PAPER)

    # ---------------------------------------------------------- masthead
    cv.rect(0, 0, W, 128, NAVY)
    text(cv, 0, 14, "THE WORLD IN FOCUS", 7, WHITE, align="center", width=W)
    cv.hline(32, 68, 960, RED, 3)
    text(cv, 32, 78, "TUESDAY, 17 NOVEMBER 2026", 3, WHITE)
    text(cv, 0, 78, "STRIKES AND SUMMITS", 3, ROSE, align="right", width=992)
    text(cv, 0, 104, "War escalates in two theatres while leaders meet "
         "in Manila.", 2, MIST, align="center", width=W)

    # -------------------------------------------------------------- lead
    cv.frame(16, 128, 992, 312, INK, 2)
    cv.rect(18, 130, 502, 308, PANEL)
    lead_scene(cv, 18, 130, 500, 308)
    cv.vline(520, 130, 308, INK, 2)
    text(cv, 536, 140, "EUROPE \u00b7 UKRAINE WAR", 2, RED)
    draw_headline(cv, 536, 160, "BRIDGE SPAN FALLS INTO THE SEA",
                  4, INK, 456, 36)
    cv.hline(536, 240, 120, RED, 3)
    para(cv, 536, 250,
         "Ukraine says its strike dropped the road arch of the 19-km "
         "Kerch Bridge. Traffic is halted. The rail arch stands; the "
         "Kremlin vows to rebuild.",
         3, INK, 456, 28)
    text(cv, 536, 422, "2ND STRIKE IN UNDER 24 HOURS", 2, RED)

    # -------------------------------------------------------- middle row
    # Gulf, left
    cv.frame(16, 440, 492, 304, INK, 2)
    cv.rect(18, 442, 488, 300, PANEL)
    gulf_strip(cv, 18, 442, 488, 54)
    cv.hline(18, 496, 488, INK, 2)
    text(cv, 32, 504, "MIDDLE EAST \u00b7 THE GULF", 2, RED)
    text(cv, 32, 524, "U.S. AND IRAN TRADE FIRE", 3, INK)
    para(cv, 32, 552,
         "Iran's drones target a U.S. radar in Bahrain \u2014 intercepted, "
         "no injuries. U.S. jets answer on Qeshm Island.",
         3, INK, 460, 26)
    para(cv, 32, 683,
         "Tankers were also hit near Hormuz; Iran's mine claims are "
         "unverified.",
         2, INK, 460, 18)
    text(cv, 32, 722, "3RD DRONE ATTACK ON BAHRAIN IN 5 DAYS", 2, RED)

    # Manila, right
    cv.frame(516, 440, 492, 304, INK, 2)
    cv.rect(518, 442, 488, 300, PANEL)
    quad_flags(cv, 542, 446, 440, 50)
    cv.hline(518, 496, 488, INK, 2)
    text(cv, 532, 504, "ASIA \u00b7 DIPLOMACY", 2, RED)
    text(cv, 532, 524, "TRUMP LANDS IN MANILA", 3, INK)
    para(cv, 532, 552,
         "First Quad summit in two years launches an AI accelerator; "
         "Thailand to scrap tariffs on U.S. goods.",
         3, INK, 460, 26)
    para(cv, 532, 683,
         "Quad also agreed deals on critical minerals.",
         2, INK, 460, 18)
    text(cv, 532, 722, "1ST QUAD LEADERS' MEETING IN 2 YEARS", 2, RED)

    # -------------------------------------------------------- bottom row
    # Nvidia, left
    cv.frame(16, 744, 492, 188, INK, 2)
    cv.rect(18, 746, 488, 184, PANEL)
    text(cv, 32, 756, "TECH \u00b7 MARKETS", 2, RED)
    draw_headline(cv, 32, 774, "NVIDIA SALES MORE THAN DOUBLE",
                  3, INK, 400, 26)
    para(cv, 32, 830,
         "$115.8B revenue, up 103%, in its first results since Huang's "
         "exit.",
         3, INK, 460, 26)
    text(cv, 32, 910, "Q4 GUIDANCE: $130B", 2, RED)
    chip_icon(cv, 452, 752, 44)

    # Chase, right
    cv.frame(516, 744, 492, 188, INK, 2)
    cv.rect(518, 746, 488, 184, PANEL)
    text(cv, 532, 756, "MONEY \u00b7 U.S. BANKS", 2, RED)
    draw_headline(cv, 532, 774, "BUG, NOT HACK, BLAMED FOR BANK OUTAGE",
                  3, INK, 400, 26)
    para(cv, 532, 830,
         "Software bug slowed Chase banking and Zelle; other banks "
         "felt delays.",
         3, INK, 460, 26)
    text(cv, 532, 910, "~4,800 REPORTS AT PEAK", 2, RED)
    bank_icon(cv, 948, 752, 44)

    # ------------------------------------------------------------ footer
    cv.rect(0, 932, W, 92, NAVY)
    cv.hline(0, 932, W, RED, 3)
    para(cv, 32, 936,
         "THE TAKEAWAY: On one day, war widened, diplomacy raced to "
         "catch up, and the world's money and machines showed both "
         "fragility and force.",
         2, WHITE, 960, 17)
    text(cv, 32, 972, "SOURCES: REUTERS \u00b7 AP \u00b7 BBC \u00b7 "
         "AL JAZEERA \u00b7 AFP", 2, MIST)
    para(cv, 32, 990,
         "ALSO: ROCKET FAILS, 40 SATELLITES LOST \u00b7 ESTONIA TO SHUT "
         "RUSSIA BORDER CROSSINGS FROM 1 DEC",
         2, MIST, 960, 16)

    return cv


def main():
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    with open(path, "wb") as fh:
        fh.write(png_bytes(build()))
    print("wrote " + path)


if __name__ == "__main__":
    main()
