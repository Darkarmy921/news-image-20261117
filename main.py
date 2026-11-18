#!/usr/bin/env python3
"""news-image-20261117: sum up 17 November 2026's world news in one image.

A Python 3.13 standard-library-only program. It draws a one-page newspaper
front page (1024 x 1024) and writes it to $MAKEFUN_OUTPUT_DIR/entry.png
(or /output/entry.png). No network, no time, no randomness: two runs write
byte-identical files.

The five stories are the day's top stories as reported in the 17 November
2026 daily briefs (see NEWS.md for sources):
  1. Ukraine strike drops the road span of the Kerch (Crimea) Bridge.
  2. A tanker is hit near the Strait of Hormuz; a third US carrier arrives.
  3. Trump lands in Manila for the ASEAN summit, en route to China.
  4. JPMorgan Chase blames a software bug for Monday's banking outage.
  5. A ULA Vulcan rocket fails, destroying 40 Amazon Leo satellites.

Everything is drawn procedurally: a small raster canvas, a 5x7 bitmap font
written out below, flat-colour scenes, and a PNG encoder built on zlib.
"""

import binascii
import os
import struct
import zlib

# ---------------------------------------------------------------- canvas

W = 1024
H = 1024

PAPER = (246, 241, 227)
INK = (17, 17, 17)
RED = (179, 38, 30)
BLUE = (29, 78, 137)
DARKBLUE = (20, 50, 79)
SKY = (191, 217, 234)
SEA = (37, 99, 168)
ORANGE = (232, 106, 23)
YELLOW = (242, 194, 0)
GREY = (138, 138, 138)
LIGHTGREY = (205, 205, 205)
WHITE = (255, 255, 255)
DARKGREY = (68, 68, 68)


class Canvas:
    """A plain RGB raster canvas with a few flat drawing primitives."""

    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)
        self.fill_rect(0, 0, w, h, bg)

    def _idx(self, x, y):
        return (y * self.w + x) * 3

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = self._idx(x, y)
            self.px[i] = c[0]
            self.px[i + 1] = c[1]
            self.px[i + 2] = c[2]

    def fill_rect(self, x, y, w, h, c):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        for yy in range(y0, y1):
            base = (yy * self.w + x0) * 3
            for xx in range(x0, x1):
                i = base + (xx - x0) * 3
                self.px[i] = c[0]
                self.px[i + 1] = c[1]
                self.px[i + 2] = c[2]

    def frame(self, x, y, w, h, c, t):
        self.fill_rect(x, y, w, t, c)
        self.fill_rect(x, y + h - t, w, t, c)
        self.fill_rect(x, y, t, h, c)
        self.fill_rect(x + w - t, y, t, h, c)

    def hline(self, x, y, w, c, t=1):
        self.fill_rect(x, y, w, t, c)

    def vline(self, x, y, h, c, t=1):
        self.fill_rect(x, y, t, h, c)

    def line(self, x0, y0, x1, y1, c, t=1):
        """Bresenham line, thickened to t pixels."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        half = t // 2
        while True:
            self.fill_rect(x0 - half, y0 - half, t, t, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def disc(self, cx, cy, r, c):
        for yy in range(cy - r, cy + r + 1):
            dy = yy - cy
            dx = int((r * r - dy * dy) ** 0.5) if r * r - dy * dy >= 0 else 0
            self.fill_rect(cx - dx, yy, dx * 2 + 1, 1, c)

    def polygon(self, pts, c):
        """Even-odd scanline fill for a simple polygon."""
        ys = [p[1] for p in pts]
        for y in range(min(ys), max(ys) + 1):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    x = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
                    xs.append(x)
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.fill_rect(int(xs[i]), y, int(xs[i + 1]) - int(xs[i]) + 1, 1, c)

    def triangle(self, x0, y0, x1, y1, x2, y2, c):
        self.polygon([(x0, y0), (x1, y1), (x2, y2)], c)


# ---------------------------------------------------------------- font
# A 5x7 bitmap font, one entry per glyph: 7 rows of 5 cells ('#' = ink).
# Only capitals, digits and the punctuation the page needs.

FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "?": ("01110", "10001", "00001", "00110", "00100", "00000", "00100"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "%": ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    "$": ("00100", "01111", "10100", "01110", "00101", "11110", "00100"),
    "&": ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    '"': ("01010", "01010", "00000", "00000", "00000", "00000", "00000"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
    "*": ("00000", "00100", "10101", "01110", "10101", "00100", "00000"),
}

# Bullet: a small solid square, drawn mid-cap-height.
BULLET = ("00000", "00000", "01100", "01100", "00000", "00000", "00000")

CHAR_W = 6  # advance per character, in font cells (5 + 1 space)


def text_width(s, scale):
    return len(s) * CHAR_W * scale - scale


def draw_char(cv, x, y, ch, scale, color):
    glyph = FONT.get(ch)
    if glyph is None:
        if ch == "\u2022":
            glyph = BULLET
        else:
            glyph = FONT[" "]
    for row in range(7):
        bits = glyph[row]
        for col in range(5):
            if bits[col] == "1":
                cv.fill_rect(x + col * scale, y + row * scale, scale, scale, color)


def draw_text(cv, x, y, s, scale, color, align="left"):
    if align == "center":
        x = x - text_width(s, scale) // 2
    elif align == "right":
        x = x - text_width(s, scale)
    cx = x
    for ch in s:
        draw_char(cv, cx, y, ch, scale, color)
        cx += CHAR_W * scale
    return cx


def wrap_text(s, scale, max_w):
    """Greedy word wrap; returns a list of lines that fit max_w."""
    lines = []
    for para in s.split("\n"):
        words = para.split(" ")
        cur = ""
        for word in words:
            trial = word if not cur else cur + " " + word
            if text_width(trial, scale) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
    return lines


def draw_block(cv, x, y, s, scale, color, max_w, line_h=None, align="left"):
    """Draw wrapped text; returns the y just below the last line."""
    if line_h is None:
        line_h = 7 * scale + scale * 2
    for line in wrap_text(s, scale, max_w):
        draw_text(cv, x, y, line, scale, color, align=align)
        y += line_h
    return y


# ---------------------------------------------------------------- PNG

def png_bytes(cv):
    """Encode the canvas as a whole PNG (colour type 2, filter 0 rows)."""

    def chunk(kind, data):
        out = struct.pack(">I", len(data)) + kind + data
        out += struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)
        raw += cv.px[y * stride:(y + 1) * stride]
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


# ---------------------------------------------------------------- scenes

def draw_kerch(cv, x, y, w, h):
    """The Crimea Bridge: deck in two pieces, the road arch down in the sea."""
    cv.fill_rect(x, y, w, h, SKY)
    sea_y = y + h - 58
    cv.fill_rect(x, sea_y, w, h - (sea_y - y), SEA)
    # waves
    for wx in range(x + 8, x + w - 8, 34):
        cv.line(wx, sea_y + 18, wx + 12, sea_y + 12, WHITE, 3)
        cv.line(wx + 12, sea_y + 12, wx + 24, sea_y + 18, WHITE, 3)
        cv.line(wx + 4, sea_y + 40, wx + 16, sea_y + 34, WHITE, 3)
        cv.line(wx + 16, sea_y + 34, wx + 28, sea_y + 40, WHITE, 3)
    deck_y = y + 96
    # deck, left and right of the gap
    gap_x0 = x + w // 2 - 78
    gap_x1 = x + w // 2 + 78
    cv.fill_rect(x, deck_y, gap_x0 - x, 14, DARKGREY)
    cv.fill_rect(gap_x1, deck_y, x + w - gap_x1, 14, DARKGREY)
    # deck posts
    for px in (x + 30, x + 130, x + w - 150, x + w - 50):
        cv.fill_rect(px, deck_y + 14, 12, sea_y - deck_y - 14, DARKGREY)
    # broken arch stubs rising from each side of the gap
    cv.line(gap_x0 - 6, deck_y, gap_x0 - 70, deck_y - 52, DARKGREY, 10)
    cv.line(gap_x1 + 6, deck_y, gap_x1 + 70, deck_y - 52, DARKGREY, 10)
    # fallen arch piece in the water, tilted
    cv.polygon(
        [
            (gap_x0 + 8, sea_y + 8),
            (gap_x1 - 8, sea_y + 26),
            (gap_x1 - 22, sea_y + 38),
            (gap_x0 - 6, sea_y + 20),
        ],
        DARKGREY,
    )
    # explosion burst over the gap
    cx, cy = x + w // 2, deck_y - 34
    cv.disc(cx, cy, 30, ORANGE)
    cv.disc(cx, cy, 19, YELLOW)
    cv.disc(cx - 6, cy - 4, 8, WHITE)
    # smoke
    cv.disc(cx - 52, cy - 26, 16, GREY)
    cv.disc(cx - 30, cy - 44, 20, LIGHTGREY)
    cv.disc(cx + 48, cy - 30, 15, GREY)
    cv.disc(cx + 26, cy - 48, 18, LIGHTGREY)
    draw_text(cv, x + 10, y + 8, "KERCH STRAIT", 2, INK)


def draw_hormuz(cv, x, y, w, h):
    """A burning tanker and a US aircraft carrier in the Strait of Hormuz."""
    cv.fill_rect(x, y, w, h, SKY)
    sea_y = y + h - 26
    cv.fill_rect(x, sea_y, w, h - (sea_y - y), SEA)
    # tanker, left
    cv.fill_rect(x + 14, sea_y - 26, 150, 26, INK)
    cv.fill_rect(x + 24, sea_y - 44, 34, 18, INK)
    cv.fill_rect(x + 110, sea_y - 38, 12, 12, INK)
    # fire plume from the tanker (kept inside the scene)
    cv.disc(x + 130, sea_y - 32, 14, ORANGE)
    cv.disc(x + 130, sea_y - 34, 9, YELLOW)
    cv.disc(x + 104, sea_y - 38, 7, GREY)
    cv.disc(x + 152, sea_y - 38, 7, LIGHTGREY)
    # carrier, right: flat deck and island tower
    cv.fill_rect(x + w - 168, sea_y - 18, 154, 18, DARKGREY)
    cv.fill_rect(x + w - 96, sea_y - 44, 26, 26, DARKGREY)
    cv.fill_rect(x + w - 92, sea_y - 52, 6, 8, DARKGREY)
    # a jet on deck
    cv.triangle(
        x + w - 150, sea_y - 24, x + w - 128, sea_y - 24,
        x + w - 139, sea_y - 34, LIGHTGREY,
    )


def draw_manila(cv, x, y, w, h):
    """Three flags on poles: the United States, the Philippines, China."""
    cv.fill_rect(x, y, w, h, SKY)
    cv.fill_rect(x, y + h - 22, w, 22, (120, 168, 90))
    poles = [
        (x + 52, "US"),
        (x + w // 2 - 8, "PH"),
        (x + w - 92, "CN"),
    ]
    for px, kind in poles:
        cv.vline(px, y + 12, h - 30, DARKGREY, 4)
        fx, fy = px + 4, y + 12
        if kind == "US":
            for i in range(7):
                cv.fill_rect(fx, fy + i * 6, 62, 6, RED if i % 2 == 0 else WHITE)
            cv.fill_rect(fx, fy, 26, 18, BLUE)
            cv.disc(fx + 13, fy + 9, 3, WHITE)
        elif kind == "PH":
            cv.fill_rect(fx, fy, 62, 42, BLUE)
            cv.fill_rect(fx, fy + 21, 62, 21, RED)
            cv.triangle(fx, fy, fx, fy + 42, fx + 26, fy + 21, WHITE)
            cv.disc(fx + 10, fy + 21, 4, YELLOW)
        else:
            cv.fill_rect(fx, fy, 62, 42, RED)
            cv.disc(fx + 12, fy + 12, 5, YELLOW)
            cv.disc(fx + 26, fy + 8, 2, YELLOW)
            cv.disc(fx + 30, fy + 16, 2, YELLOW)
            cv.disc(fx + 24, fy + 24, 2, YELLOW)


def draw_bank_icon(cv, x, y, s):
    """A small bank building, s x s."""
    cv.fill_rect(x, y, s, s, PAPER)
    cv.triangle(x + 4, y + 26, x + s - 4, y + 26, x + s // 2, y + 6, DARKGREY)
    for cx in (x + 12, x + s // 2 - 5, x + s - 22):
        cv.fill_rect(cx, y + 30, 10, s - 44, DARKGREY)
    cv.fill_rect(x + 6, y + s - 14, s - 12, 8, DARKGREY)
    draw_text(cv, x + s // 2, y + s - 34, "$", 2, RED, align="center")


def draw_rocket_icon(cv, x, y, s):
    """A small rocket failing on a dark sky, s x s."""
    cv.fill_rect(x, y, s, s, DARKBLUE)
    # falling satellites
    for sx, sy in ((x + 8, y + 12), (x + s - 20, y + 26), (x + 16, y + 44)):
        cv.fill_rect(sx, sy, 10, 6, YELLOW)
        cv.fill_rect(sx + 10, sy + 2, 6, 2, YELLOW)
    # rocket body, tilted
    cx = x + s // 2
    cv.polygon(
        [(cx - 8, y + 34), (cx + 8, y + 34), (cx + 6, y + 70), (cx - 6, y + 70)],
        WHITE,
    )
    cv.triangle(cx - 8, y + 34, cx + 8, y + 34, cx, y + 14, RED)
    cv.triangle(cx - 8, y + 62, cx - 18, y + 76, cx - 6, y + 70, RED)
    cv.triangle(cx + 8, y + 62, cx + 18, y + 76, cx + 6, y + 70, RED)
    # burst below
    cv.disc(cx, y + 84, 10, ORANGE)
    cv.disc(cx, y + 84, 5, YELLOW)


# ---------------------------------------------------------------- page

def panel(cv, x, y, w, h, kicker, kicker_color=RED):
    cv.fill_rect(x, y, w, h, PAPER)
    cv.frame(x, y, w, h, INK, 4)
    draw_text(cv, x + 14, y + 12, kicker, 3, kicker_color)
    return y + 12 + 7 * 3 + 10


def build():
    cv = Canvas(W, H, PAPER)
    cv.frame(0, 0, W, H, INK, 6)

    # --- masthead
    draw_text(cv, W // 2, 16, "THE WORLD TODAY", 9, INK, align="center")
    cv.hline(24, 90, W - 48, RED, 6)
    draw_text(cv, W // 2, 102, "TUESDAY, 17 NOVEMBER 2026", 5, INK, align="center")

    # --- lead story: the Crimea Bridge
    lx, ly, lw, lh = 12, 148, 1000, 368
    cv.fill_rect(lx, ly, lw, lh, PAPER)
    cv.frame(lx, ly, lw, lh, INK, 4)
    draw_text(cv, lx + 14, ly + 12, "LEAD STORY - UKRAINE WAR", 3, RED)
    draw_text(cv, lx + 14, ly + 40, "CRIMEA BRIDGE SPAN", 6, INK)
    draw_text(cv, lx + 14, ly + 84, "FALLS INTO THE SEA", 6, INK)
    draw_kerch(cv, lx + 14, ly + 136, 560, 218)
    cap_x = lx + 590
    y = draw_block(
        cv, cap_x, ly + 144,
        "UKRAINE SAYS ITS STRIKE DROPPED THE ROAD ARCH OF THE 19-KM KERCH BRIDGE.",
        3, INK, 396, line_h=26,
    )
    draw_block(
        cv, cap_x, y + 6,
        "THE RAIL BRIDGE STILL STANDS. TRAFFIC IS HALTED. THE KREMLIN VOWS TO REBUILD.",
        3, INK, 396, line_h=26,
    )

    # --- second row: Hormuz and Manila
    ry, rh, rw = 524, 236, 488
    # Hormuz
    hx = 12
    ty = panel(cv, hx, ry, rw, rh, "MIDDLE EAST - HORMUZ")
    draw_hormuz(cv, hx + 14, ty, rw - 28, 64)
    y = draw_block(cv, hx + 14, ty + 72,
                   "TANKER HIT AS 3RD CARRIER ARRIVES", 4, INK, rw - 28,
                   line_h=30)
    draw_block(cv, hx + 14, y + 4,
               "MINES ARE BLAMED. IRAN'S CLAIMS ARE UNVERIFIED.", 3, INK,
               rw - 28, line_h=21)
    # Manila
    mx = 524
    ty = panel(cv, mx, ry, rw, rh, "ASIA - SUMMIT DIPLOMACY")
    draw_manila(cv, mx + 14, ty, rw - 28, 64)
    y = draw_block(cv, mx + 14, ty + 72,
                   "TRUMP LANDS IN MANILA", 4, INK, rw - 28,
                   line_h=30)
    draw_block(cv, mx + 14, y + 4,
               "FOR THE ASIA SUMMIT. THEN XI AND PUTIN.", 3, INK,
               rw - 28, line_h=21)

    # --- third row: JPMorgan and Vulcan
    by, bh = 768, 180
    # JPMorgan
    bx = 12
    ty = panel(cv, bx, by, rw, bh, "MONEY - U.S. BANKS")
    draw_bank_icon(cv, bx + 14, ty + 4, 92)
    y = draw_block(cv, bx + 118, ty + 4,
                   "BUG BLAMED FOR OUTAGE", 4, INK, rw - 122,
                   line_h=30)
    draw_block(cv, bx + 118, y + 4,
               "CHASE: BUG SLOWED BANKING AND ZELLE. NOT A CYBERATTACK.",
               3, INK, rw - 122, line_h=21)
    # Vulcan
    vx = 524
    ty = panel(cv, vx, by, rw, bh, "SPACE - SATELLITES")
    draw_rocket_icon(cv, vx + 14, ty + 4, 92)
    y = draw_block(cv, vx + 118, ty + 4,
                   "ROCKET FAILS, 40 LOST", 4, INK, rw - 122,
                   line_h=30)
    draw_block(cv, vx + 118, y + 4,
               "VULCAN FAILED. 40 SATELLITES LOST.",
               3, INK, rw - 122, line_h=21)

    # --- footer ticker
    fy = 956
    cv.fill_rect(12, fy, 1000, 56, INK)
    draw_text(cv, W // 2, fy + 6,
              "ALSO: ESTONIA TO SHUT RUSSIA BORDER CROSSINGS", 3, WHITE,
              align="center")
    draw_text(cv, W // 2, fy + 31,
              "FROM 1 DEC - NVIDIA REPORTS AFTER HUANG EXIT", 3, WHITE,
              align="center")
    return cv


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    data = png_bytes(build())
    with open(os.path.join(out_dir, "entry.png"), "wb") as f:
        f.write(data)


if __name__ == "__main__":
    main()
