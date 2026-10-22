#!/usr/bin/env python3
"""
cat_widgets.py - animated pixel-cat widgets for a GitHub profile README.

Everything here is original pixel art drawn as SVG, so nothing is hot-linked
from other sites and nothing can break when a third-party service goes down.

Commands
  update        fetch contribution data from the GitHub API, then render every widget
  render        re-render every widget from the cached data (no network)
  feed          record a visitor feeding the cat (used by .github/workflows/feed-the-cat.yml)
  card-options  print themed options for the GitHub Readme Stats action (for $GITHUB_OUTPUT)
  demo          render everything with made-up data into ./demo-preview (for local previews)

Only the Python standard library is used (Python 3.9+).
Settings live in cat.config.json in the repository root.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import random
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "cat.config.json"
OUT_DIR = ROOT / "profile"

SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"

# --------------------------------------------------------------------------------------
# Themes (Catppuccin flavours - yes, the palette is named after cats)
# --------------------------------------------------------------------------------------
_NAMES = ("rosewater flamingo pink mauve red maroon peach yellow green teal sky sapphire blue "
          "lavender text subtext1 subtext0 overlay2 overlay1 overlay0 surface2 surface1 surface0 "
          "base mantle crust").split()
_FLAVOURS = {
    "mocha": "F5E0DC F2CDCD F5C2E7 CBA6F7 F38BA8 EBA0AC FAB387 F9E2AF A6E3A1 94E2D5 89DCEB 74C7EC "
             "89B4FA B4BEFE CDD6F4 BAC2DE A6ADC8 9399B2 7F849C 6C7086 585B70 45475A 313244 1E1E2E "
             "181825 11111B",
    "macchiato": "F4DBD6 F0C6C6 F5BDE6 C6A0F6 ED8796 EE99A0 F5A97F EED49F A6DA95 8BD5CA 91D7E3 7DC4E4 "
                 "8AADF4 B7BDF8 CAD3F5 B8C0E0 A5ADCB 939AB7 8087A2 6E738D 5B6078 494D64 363A4F 24273A "
                 "1E2030 181926",
    "frappe": "F2D5CF EEBEBE F4B8E4 CA9EE6 E78284 EA999C EF9F76 E5C890 A6D189 81C8BE 99D1DB 85C1DC "
              "8CAAEE BABBF1 C6D0F5 B5BFE2 A5ADCE 949CBB 838BA7 737994 626880 51576D 414559 303446 "
              "292C3C 232634",
    "latte": "DC8A78 DD7878 EA76CB 8839EF D20F39 E64553 FE640B DF8E1D 40A02B 179299 04A5E5 209FB5 "
             "1E66F5 7287FD 4C4F69 5C5F77 6C6F85 7C7F93 8C8FA1 9CA0B0 ACB0BE BCC0CC CCD0DA EFF1F5 "
             "E6E9EF DCE0E8",
}
THEMES = {k: dict(zip(_NAMES, v.split())) for k, v in _FLAVOURS.items()}

DEFAULT_CONFIG = {
    "github_username": "",
    "name": "Your Name",
    "headline": "Software Engineer",
    "subline": "",
    "status_pill": "",
    "terminal_title": "",
    "prompt_path": "~",
    "chips": [],
    "timezone": "UTC",
    "timezone_label": "",
    "theme": "mocha",
    "theme_overrides": {},
    "cat": {
        "name": "Miao",
        "fur": "FAB387", "stripes": "E08D5C", "belly": "F5E0DC", "inner_ear": "F5C2E7",
        "nose": "EBA0AC", "eyes": "11111B", "outline": "11111B", "collar": "CBA6F7", "charm": "F9E2AF",
    },
    "footer": {
        "title": "Thanks for stopping by!",
        "subtitle": "Come back soon. The cat will still be here, probably asleep.",
        "command": 'git commit -m "see you next commit"',
    },
    "pet": {
        "title": "*purrrrrr*",
        "subtitle": "You pet the cat. The cat approves.",
        "footnote": "+1 happiness   +1 dev morale   -1 bug",
    },
    "feed": {"cooldown_hours": 12},
    "oracle": {"title": "THE MIAORICLE SAYS", "quotes": [], "use_builtin_quotes": True},
    "moods": {"on_a_roll_streak": 5, "on_a_roll_week": 20, "coding_days": 3,
              "napping_days": 14, "snack_hours": 3},
    "cards": {"stats_title": "", "langs_title": "Most Used Languages", "langs_count": 8,
              "exclude_repos": [], "wakatime_title": "This Week in My Editor"},
}


def deep_merge(base: dict, extra: dict) -> dict:
    out = dict(base)
    for k, v in (extra or {}).items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config() -> dict:
    user = {}
    if CONFIG_FILE.exists():
        user = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    cfg = deep_merge(DEFAULT_CONFIG, user)
    if not cfg.get("github_username"):
        cfg["github_username"] = os.environ.get("GITHUB_REPOSITORY_OWNER", "")
    return cfg


def hexc(value: str) -> str:
    v = str(value).strip().lstrip("#").upper()
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    if len(v) != 6 or any(c not in "0123456789ABCDEF" for c in v):
        raise ValueError(f"not a hex colour: {value!r}")
    return v


def mix(a: str, b: str, t: float) -> str:
    a, b = hexc(a), hexc(b)
    ca = [int(a[i:i + 2], 16) for i in (0, 2, 4)]
    cb = [int(b[i:i + 2], 16) for i in (0, 2, 4)]
    return "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(ca, cb))


def get_theme(cfg: dict) -> dict:
    name = str(cfg.get("theme", "mocha")).lower()
    if name not in THEMES:
        print(f"::warning::Unknown theme {name!r}; using mocha")
        name = "mocha"
    theme = dict(THEMES[name])
    for k, v in (cfg.get("theme_overrides") or {}).items():
        if not k.startswith("_"):
            theme[k] = hexc(v)
    theme.setdefault("accent", theme["mauve"])
    theme["accent"] = hexc(theme["accent"])
    return theme


def sprite_colors(cfg: dict, t: dict) -> dict:
    cat = cfg["cat"]
    c = {k: hexc(v) for k, v in cat.items() if k != "name"}
    return {
        "K": c["outline"], "O": c["fur"], "o": c["stripes"], "C": c["belly"],
        "c": mix(c["belly"], c["stripes"], 0.25), "P": c["inner_ear"], "N": c["nose"],
        "e": c["eyes"], "W": "FFFFFF", "Z": "FFFFFF", "E": t["green"], "G": c["collar"], "Y": c["charm"],
        "B": t["surface1"], "b": t["surface0"], "S": t["crust"], "D": t["surface2"],
        "d": t["surface1"], "k": t["surface0"], "V": t["lavender"], "v": t["blue"],
        "R": t["red"], "r": mix(t["red"], "000000", 0.22), "T": t["overlay0"], "H": t["red"],
        "M": t["text"], "F": "A87B5D", "X": t["accent"], "A": t["peach"], "a": t["yellow"],
        "g": t["green"], "s": t["sky"],
    }


# --------------------------------------------------------------------------------------
# Pixel sprites (ASCII art; "." is transparent)
# --------------------------------------------------------------------------------------
def mirror(half):
    return [row + row[::-1] for row in half]


def blank(w, h):
    return ["." * w for _ in range(h)]


def overlay(base, top, ox=0, oy=0):
    rows = [list(r) for r in base]
    for y, line in enumerate(top):
        for x, ch in enumerate(line):
            yy, xx = y + oy, x + ox
            if ch != "." and 0 <= yy < len(rows) and 0 <= xx < len(rows[0]):
                rows[yy][xx] = ch
    return ["".join(r) for r in rows]


def fill(rows, x0, y0, x1, y1, ch):
    rows = [list(r) for r in rows]
    for y in range(max(0, y0), min(len(rows), y1 + 1)):
        for x in range(max(0, x0), min(len(rows[0]), x1 + 1)):
            rows[y][x] = ch
    return ["".join(r) for r in rows]


def diff(old, new):
    """Pixels that changed between two sprites, as an overlay sprite."""
    return ["".join(n if n != o else "." for o, n in zip(ro, rn)) for ro, rn in zip(old, new)]


SIT_HALF = [
    "...K..........", "...KK.........", "..KOPK........", "..KOPPK.......", "..KOPPPK......",
    ".KOOPPOOKKKKKK", ".KOOOOOOOOOoOo", "KOOOOOOOOOOoOo", "KOOOOOOOOOOOOO", "KOOOOOOOOOOOOO",
    "KOOOWeOOOOOOOO", "KOOOeeOOOOOOOO", "KOOOeeOOOOOOOO", "KOOOOOOOOOOOOO", "KCCOOOOOOOOCCN",
    "KCCCOOOOOOCKCK", ".KCCCOOOOOCCKC", "..KKCCOOOOCCCC", "....KOOGGGGGGG", "...KOOOOCCCCCY",
    "...KOOOOCCCCCY", "..KOOoOOOCCCCC", "..KOOOoOOCCCCC", "..KOOOOOOOCCCC", ".KOOOoOOOOCCCC",
    ".KOOOOoOOOCCCC", ".KOOOOOOOOCCCC", ".KOOOOOOKKKCCC", ".KOOOOOKCCCKCC", ".KOOOOOKCPCKCC",
    "..KKKKKKKKKKKK",
]
SIT = mirror(SIT_HALF)  # 28 x 31

TAILS = [
    ["..KKK..", ".KOoOK.", ".KOKKK.", ".KOOK..", "..KoOK.", "..KOOK.", "..KOOK.", ".KOoOK.",
     "KOOOK..", "OOOK...", "KKK...."],
    ["...KK..", "..KOoK.", "..KOOK.", ".KOOK..", ".KoOK..", ".KOOK..", ".KOOK..", ".KOoOK.",
     "KOOOK..", "OOOK...", "KKK...."],
    [".KKK...", "KOoOK..", "KKKOK..", "..KOOK.", "..KoOK.", "..KOOK.", "..KOOK.", ".KOoOK.",
     "KOOOK..", "OOOK...", "KKK...."],
]

_EYE_PATTERNS = {
    "open": ["We", "ee", "ee"],
    "down": ["OO", "We", "ee"],
    "blink": ["OO", "OO", "KK"],
    "glow": ["WE", "EE", "EE"],
}


def with_eyes(rows, kind, top=10, inset=4):
    """Swap the eyes of the big sitting cat (eyes live at rows 10-12)."""
    rows = [list(r) for r in rows]
    w = len(rows[0])
    for dy in range(3):  # clear
        for x in (inset, inset + 1):
            rows[top + dy][x] = "O"
            rows[top + dy][w - 1 - x] = "O"
    if kind == "happy":
        for dy, line in enumerate(["OKO", "KOK", "OOO"]):
            for dx, ch in enumerate(line):
                rows[top + dy][inset - 1 + dx] = ch
                rows[top + dy][w - 1 - (inset - 1 + dx)] = ch
    else:
        for dy, line in enumerate(_EYE_PATTERNS[kind]):
            for dx, ch in enumerate(line):
                rows[top + dy][inset + dx] = ch
                rows[top + dy][w - inset - 2 + dx] = ch
    return ["".join(r) for r in rows]


MINI = mirror(["K.....", "KK....", "KPK...", "KPOKKK", "KOOOOo", "KOWeOO", "KOeeOO", "KCCOOO",
               "KCCOCN", ".KCCCC", "..KKKK"])  # 12 x 11


def mini_eyes(rows, kind):
    pats = {"open": ["We", "ee"], "closed": ["OO", "KK"], "happy": ["KK", "OO"]}
    rows = [list(r) for r in rows]
    w = len(rows[0])
    for dy in range(2):
        for dx in range(2):
            rows[5 + dy][2 + dx] = pats[kind][dy][dx]
            rows[5 + dy][w - 4 + dx] = pats[kind][dy][dx]
    return ["".join(r) for r in rows]


WALK_BODY = [".KK............", "KOOK...........", "KoOK...........", ".KOOK..........",
             "..KOK.KKKKKKK..", "...KOKOOOOoOOK.", "...KOOOoOOOOoOK", "...KOOOOOOOOOOK",
             "....KOOOOOOOOOK"]
WALK_LEGS = {
    "A": ["....KOK.KOK..KOK.KOK..", "....KCK.KCK..KCK.KCK..", "....KKK.KKK..KKK.KKK.."],
    "B": [".....KOKOK....KOKOK...", ".....KCKCK....KCKCK...", ".....KKKKK....KKKKK..."],
}


def walker(frame="A", eyes="open"):
    rows = blank(24, 15)
    rows = overlay(rows, WALK_BODY, 0, 3)
    rows = overlay(rows, WALK_LEGS[frame], 0, 12)
    return overlay(rows, mini_eyes(MINI, eyes), 11, 1)


SLEEP_BODY = {
    "out": ["......KKKKKKKKK......", "...KKKOOOOoOOOOKKK...", "..KOOOOoOOOOOoOOOOK..",
            ".KOOOOOOOOOOOOOOOOOK.", "KOOOOOOOOOOOOOOOOOOOK", "KOOOOOOOOOOOOOOOOOOOK",
            "KOOOOOOOOOOOOOOOOOOOK", "KOOOOOOOOOOOOOOOOOOOK", "KOOOOOOOOOOOOOOOOOOOK",
            "KKKKKKKKKKKKKKKKKKKKK"],
    "in": [".....................", "......KKKKKKKKK......", "...KKKOOOOoOOOOKKK...",
           ".KKOOOOoOOOOOoOOOOKK.", "KOOOOOOOOOOOOOOOOOOOK", "KOOOOOOOOOOOOOOOOOOOK",
           "KOOOOOOOOOOOOOOOOOOOK", "KOOOOOOOOOOOOOOOOOOOK", "KOOOOOOOOOOOOOOOOOOOK",
           "KKKKKKKKKKKKKKKKKKKKK"],
}
SLEEP_TAIL = ["..KKKKKKKKKKKKKKKKKKKKKKKK.", ".KOOoOOOoOOOoOOOoOOOOOOOOOK",
              "..KKKKKKKKKKKKKKKKKKKKKKKK."]


def sleeper(breath="out"):
    rows = blank(31, 15)
    rows = overlay(rows, SLEEP_BODY[breath], 9, 2)
    rows = overlay(rows, mini_eyes(MINI, "closed"), 1, 1)
    return overlay(rows, SLEEP_TAIL, 2, 11)


BALL = [".....KKKKKK.....", "...KKVVVVVVKK...", "..KVVZZVVVVVVK..", ".KVVZVVVVVVVVVK.",
        ".KVZVVVVVVVVVVK.", "KVVVVVVVVVVVvvVK", "KVVVVVVVVVVvvvVK", "KVVVVVVVVVvvvvVK",
        "KVVVVVVVVvvvvvVK", ".KVVVVVVvvvvvvK.", ".KVVVVvvvvvvvVK.", "..KKVVVVVVVVKK..",
        "...TKKKKKKKKT...", "..KTTTTTTTTTTK..", ".KTTGGGGGGGGTTK.", ".KKKKKKKKKKKKKK."]
BOWL_FULL = ["...MM.M.MM.MM...", "..MFMMFMMFMMFM..", "KKKKKKKKKKKKKKKK", "KRRRRRRRRRRRRRRK",
             ".KRRRMRRRRMRRRK.", "..KrrrrrrrrrrK..", "...KKKKKKKKKK..."]
BOWL_EMPTY = ["KKKKKKKKKKKKKKKK", "KRRRRRRRRRRRRRRK", ".KRRRMRRRRMRRRK.", "..KrrrrrrrrrrK..",
              "...KKKKKKKKKK..."]
HEART = [".HH.HH.", "HHHHHHH", "HHHHHHH", ".HHHHH.", "..HHH..", "...H..."]
FISH = ["...KKKK...K.", "..KvvvvK.KvK", ".KvZvvvvKvvK", "KvvvvvvvvvK.", ".KvvvvvvKvvK",
        "..KvvvvK.KvK", "...KKKK...K."]
PAW = [".X.X.", "X...X", "..X..", ".XXX.", ".XXX."]
FLAME = ["...A..", "..AA..", "..AaA.", ".AaaA.", ".AaaaA", "AaaZaA", "AaaaaA", ".AAAA."]
BUBBLE = ["..KKKKKKKKKK..", ".KMMMMMMMMMMK.", "KMMMMMMMMMMMMK", "KMMMMMMMMMMMMK", "KMMMMMMMMMMMMK",
          "KMMMMMMMMMMMMK", ".KMMMMMMMMMMK.", "..KKKKKMKKKK..", "......KMK.....", "......KK......"]
SPARK = ["..g..", "..g..", "gg.gg", "..g..", "..g.."]


def sit_pose(eyes="open", tail=None, prop=None):
    """Big sitting cat on a 34 x 36 canvas, optional tail frame and prop in front."""
    rows = overlay(blank(34, 36), with_eyes(SIT, eyes), 0, 0)
    if tail is not None:
        rows = overlay(rows, TAILS[tail], 26, 20)
    if prop == "ball":
        rows = overlay(rows, BALL, 6, 19)
        rows = overlay(rows, [".KKK", "KCCK", "KCCK", ".KK."], 3, 25)
        rows = overlay(rows, ["KKK.", "KCCK", "KCCK", ".KK."], 19, 25)
    elif prop == "bowl_full":
        rows = overlay(rows, BOWL_FULL, 6, 26)
    elif prop == "bowl_empty":
        rows = overlay(rows, BOWL_EMPTY, 6, 28)
    return rows


def laptop_rows():
    r = blank(60, 47)
    r = fill(r, 10, 14, 49, 39, "K")
    r = fill(r, 11, 15, 48, 38, "B")
    r = fill(r, 13, 17, 46, 35, "S")
    r = fill(r, 29, 15, 30, 15, "b")
    r = fill(r, 11, 38, 48, 38, "b")
    for y, (x0, x1, ch) in enumerate([(8, 51, "D"), (7, 52, "D"), (6, 53, "D"), (5, 54, "D"),
                                      (4, 55, "d")]):
        r = fill(r, x0, 40 + y, x1, 40 + y, "K")
        r = fill(r, x0 + 1, 40 + y, x1 - 1, 40 + y, ch)
    r = fill(r, 4, 45, 55, 45, "K")
    rows = [list(x) for x in r]
    for x in range(10, 50, 2):
        rows[41][x] = "k"
    for x in range(9, 51, 2):
        rows[42][x] = "k"
    r = ["".join(x) for x in rows]
    return fill(r, 25, 43, 34, 43, "B")


def laptop_paw(side, up):
    r = blank(60, 47)
    top, paw_y = 30, (37 if up else 39)
    x0, x1 = (5, 9) if side == "L" else (50, 54)
    for y in range(top, paw_y):
        inset = 0 if y > top + 2 else 1
        if side == "L":
            r = fill(r, x0 + 1 + inset, y, x1, y, "O")
            r = fill(r, x0 + inset, y, x0 + inset, y, "K")
        else:
            r = fill(r, x0, y, x1 - 1 - inset, y, "O")
            r = fill(r, x1 - inset, y, x1 - inset, y, "K")
    sx = x0 + 3 if side == "L" else x1 - 3
    r = fill(r, sx, top + 4, sx, top + 4, "o")
    r = fill(r, sx, top + 6, sx, top + 6, "o")
    r = fill(r, x0, paw_y, x1, paw_y + 2, "K")
    r = fill(r, x0 + 1, paw_y, x1 - 1, paw_y + 1, "C")
    return fill(r, x0 + 2, paw_y + 1, x0 + 2, paw_y + 1, "c")


def peek_head(eyes="open"):
    return overlay(blank(60, 47), with_eyes(SIT, eyes)[:14], 16, 0)


# Code shown on the laptop screen: (x0, x1, theme colour) per token, in screen pixels.
CODE_LINES = [
    [(0, 4, "mauve"), (6, 10, "blue"), (12, 13, "overlay2")],
    [(2, 6, "blue"), (8, 14, "green"), (16, 17, "overlay2")],
    [(2, 4, "mauve"), (6, 13, "yellow"), (15, 20, "green")],
    [(4, 9, "sky"), (11, 16, "peach")],
    [(2, 3, "overlay2")],
    [(0, 3, "mauve"), (5, 10, "blue"), (12, 13, "overlay2")],
    [(2, 8, "green"), (10, 12, "pink")],
    [(0, 1, "overlay2")],
]

# --------------------------------------------------------------------------------------
# SVG helpers
# --------------------------------------------------------------------------------------
REDUCED_MOTION = "@media (prefers-reduced-motion: reduce){*{animation:none!important}}"


def esc(s) -> str:
    return _xml_escape(str(s), {'"': "&quot;"})


def f2(v) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


def sprite(rows, colors, x=0, y=0, s=1.0, cls="", extra=""):
    paths = {}
    for yy, row in enumerate(rows):
        xx, n = 0, len(row)
        while xx < n:
            ch = row[xx]
            if ch in ". ":
                xx += 1
                continue
            start = xx
            while xx < n and row[xx] == ch:
                xx += 1
            paths.setdefault(ch, []).append(f"M{start} {yy}h{xx - start}v1h-{xx - start}z")
    if not paths:
        return ""
    attrs = f' class="{cls}"' if cls else ""
    out = [f'<g{attrs}{extra}><g transform="translate({f2(x)} {f2(y)}) scale({f2(s)})" '
           f'shape-rendering="crispEdges">']
    for ch, segs in paths.items():
        out.append(f'<path fill="#{colors[ch]}" d="{"".join(segs)}"/>')
    out.append("</g></g>")
    return "".join(out)


def text(x, y, s, size, fill_hex, weight=400, family=SANS, anchor="start", extra=""):
    fam = family.replace('"', "'")
    return (f'<text x="{f2(x)}" y="{f2(y)}" font-family="{fam}" font-size="{f2(size)}" '
            f'font-weight="{weight}" fill="#{fill_hex}" text-anchor="{anchor}"{extra}>{esc(s)}</text>')


def text_w(s, size, mono=False) -> float:
    if mono:
        return len(s) * size * 0.6
    w = 0.0
    for ch in s:
        if ch in "il.,:;'|!":
            w += 0.28
        elif ch in "mwMW@%":
            w += 0.86
        elif ch.isupper() or ch.isdigit():
            w += 0.64
        elif ch == " ":
            w += 0.28
        else:
            w += 0.54
    return w * size * 1.12  # conservative: real fonts run 0-20% wider than this estimate


def wrap_px(s, size, max_w, mono=False):
    """Word-wrap by estimated rendered width (fonts differ per platform, so keep some slack)."""
    words, lines, cur = str(s).split(), [], ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if cur and text_w(cand, size, mono) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def clip_text(s, n):
    s = str(s)
    return s if len(s) <= n else s[: max(1, n - 1)] + "…"


def cycle_css(cls, n_frames, period, order=None):
    """CSS that shows frame classes cls0..clsN one at a time, in `order`, forever."""
    order = order or list(range(n_frames))
    slots = len(order)
    css = []
    for f in range(n_frames):
        kf = "".join(f"{i * 100 / slots:.3f}%{{opacity:{1 if o == f else 0}}}" for i, o in enumerate(order))
        kf += f"100%{{opacity:{1 if order[0] == f else 0}}}"
        css.append(f"@keyframes {cls}{f}{{{kf}}}")
        css.append(f".{cls}{f}{{opacity:{1 if order[0] == f else 0};"
                   f"animation:{cls}{f} {f2(period)}s step-end infinite}}")
    return "".join(css)


def blink_css(cls, period=4.6, at=0.93, length=0.035):
    a, b = at * 100, (at + length) * 100
    return (f"@keyframes {cls}{{0%,{a:.2f}%{{opacity:0}}{a + 0.01:.2f}%,{b:.2f}%{{opacity:1}}"
            f"{b + 0.01:.2f}%,100%{{opacity:0}}}}.{cls}{{opacity:0;animation:{cls} {f2(period)}s linear infinite}}")


def svg_doc(w, h, body, css="", title="", desc="", defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-labelledby="title desc">'
            f'<title id="title">{esc(title)}</title><desc id="desc">{esc(desc)}</desc>'
            f'<style>{css}{REDUCED_MOTION}</style>'
            f'{"<defs>" + defs + "</defs>" if defs else ""}{body}</svg>\n')


def card(w, h, t, rx=16):
    return (f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="{rx}" fill="#{t["base"]}" '
            f'stroke="#{t["surface0"]}" stroke-width="2"/>')


def pill(x, y, label, color, t, size=11.5, pulse_cls="pulse"):
    w = text_w(label, size, mono=True) + 34
    return (f'<rect x="{f2(x)}" y="{f2(y)}" width="{f2(w)}" height="24" rx="12" fill="#{color}" '
            f'fill-opacity=".12" stroke="#{color}" stroke-opacity=".55"/>'
            f'<circle cx="{f2(x + 14)}" cy="{f2(y + 12)}" r="4" fill="#{color}"/>'
            f'<circle class="{pulse_cls}" cx="{f2(x + 14)}" cy="{f2(y + 12)}" r="4" fill="none" '
            f'stroke="#{color}" stroke-width="2"/>'
            + text(x + 25, y + 16.5, label, size, color, 700, MONO)), w


PULSE_CSS = (".pulse{transform-box:fill-box;transform-origin:center;animation:pulse 2s ease-out infinite}"
             "@keyframes pulse{0%{transform:scale(1);opacity:.9}100%{transform:scale(2.2);opacity:0}}")


# --------------------------------------------------------------------------------------
# Re-usable animated scenes
# --------------------------------------------------------------------------------------
def laptop_scene(x, y, s, C, t, p="lp", paw_period=0.36, sparkles=False):
    """Cat peeking over a laptop and typing. Returns (svg, css)."""
    parts, css = [], []
    for i, tail in enumerate(TAILS):
        parts.append(sprite(overlay(blank(60, 47), tail, 43, 4), C, x, y, s, f"{p}t{i}"))
    css.append(cycle_css(f"{p}t", 3, 1.8, [0, 1, 2, 1]))
    head = peek_head("open")
    parts.append(sprite(head, C, x, y, s))
    parts.append(sprite(diff(head, peek_head("blink")), C, x, y, s, f"{p}bl"))
    css.append(blink_css(f"{p}bl", 4.2))
    parts.append(sprite(laptop_rows(), C, x, y, s))
    # code being typed on the screen
    sx, sy = x + 15 * s, y + 19 * s
    code, covers = [], []
    speed, gap, t0 = 22.0, 0.12, 0.25
    period = 7.0
    starts = []
    for line in CODE_LINES:
        length = max(b for _, b, _ in line) + 1
        starts.append((t0, length))
        t0 += length / speed + gap
    for i, line in enumerate(CODE_LINES):
        ly = sy + i * 2 * s
        for a, b, col in line:
            code.append(f'<rect x="{f2(sx + a * s)}" y="{f2(ly)}" width="{f2((b - a + 1) * s)}" '
                        f'height="{f2(s)}" fill="#{t[col]}"/>')
        start, length = starts[i]
        a_pct = start / period * 100
        b_pct = (start + length / speed) / period * 100
        covers.append(f'<rect class="{p}c{i}" x="{f2(sx - 0.5)}" y="{f2(ly - 0.5)}" '
                      f'width="{f2(length * s + 1)}" height="{f2(s + 1)}" fill="#{t["crust"]}"/>')
        css.append(f"@keyframes {p}c{i}{{0%{{transform:scaleX(1)}}{a_pct:.2f}%{{transform:scaleX(1);"
                   f"animation-timing-function:steps({length},end)}}{b_pct:.2f}%,90%{{transform:scaleX(0)}}"
                   f"90.01%,100%{{transform:scaleX(1)}}}}"
                   f".{p}c{i}{{transform:scaleX(0);transform-box:fill-box;transform-origin:right center;"
                   f"animation:{p}c{i} {f2(period)}s step-end infinite}}")
    parts.append(f'<g shape-rendering="crispEdges">{"".join(code)}{"".join(covers)}</g>')
    for i, left_up in enumerate((False, True)):
        frame = overlay(laptop_paw("L", left_up), laptop_paw("R", not left_up))
        parts.append(sprite(frame, C, x, y, s, f"{p}p{i}"))
    css.append(cycle_css(f"{p}p", 2, paw_period))
    if sparkles:
        for i, (dx, dy) in enumerate(((8, 2), (52, 9), (4, 20))):
            parts.append(sprite(SPARK, C, x + dx * s, y + dy * s, s * 0.8, f"{p}sp",
                                f' style="animation-delay:-{i * 0.5:.1f}s"'))
        css.append(f".{p}sp{{transform-box:fill-box;transform-origin:center;animation:{p}sp 1.6s ease-in-out infinite}}"
                   f"@keyframes {p}sp{{0%,100%{{opacity:0;transform:scale(.4)}}50%{{opacity:1;transform:scale(1)}}}}")
    return "".join(parts), "".join(css)


def sleeper_scene(x, y, s, C, t, p="sl", zzz=True):
    parts, css = [], []
    for i, breath in enumerate(("out", "in")):
        parts.append(sprite(sleeper(breath), C, x, y, s, f"{p}b{i}"))
    css.append(cycle_css(f"{p}b", 2, 2.8))
    if zzz:
        for i, size in enumerate((12, 16, 21)):
            zx, zy = x + (6 + i * 3) * s, y - 1 * s
            parts.append(text(zx, zy, "z", size * s / 5, t["lavender"], 800, SANS,
                              extra=f' class="{p}z" style="animation-delay:{i * 0.9:.1f}s"'))
        css.append(f".{p}z{{opacity:0;animation:{p}z 2.7s ease-in-out infinite}}"
                   f"@keyframes {p}z{{0%{{opacity:0;transform:translate(0,0)}}20%{{opacity:1}}"
                   f"100%{{opacity:0;transform:translate({f2(4 * s)}px,{f2(-7 * s)}px)}}}}")
    return "".join(parts), "".join(css)


def sit_scene(x, y, s, C, t, p="st", eyes="open", prop=None, hearts=False, bubble=False):
    parts, css = [], []
    body = sit_pose(eyes, None, prop)
    parts.append(sprite(body, C, x, y, s))
    for i in range(3):
        parts.append(sprite(overlay(blank(34, 36), TAILS[i], 26, 20), C, x, y, s, f"{p}t{i}"))
    css.append(cycle_css(f"{p}t", 3, 2.0, [0, 1, 2, 1]))
    if eyes in ("open", "glow"):
        parts.append(sprite(diff(body, sit_pose("blink", None, prop)), C, x, y, s, f"{p}bl"))
        css.append(blink_css(f"{p}bl", 5.0, 0.9))
    if hearts:
        for i, dx in enumerate((4, 20, 12)):
            parts.append(sprite(HEART, C, x + dx * s, y + 2 * s, s * 0.7, f"{p}h",
                                f' style="animation-delay:{i * 0.8:.1f}s"'))
        css.append(f".{p}h{{opacity:0;animation:{p}h 2.4s ease-out infinite}}"
                   f"@keyframes {p}h{{0%{{opacity:0;transform:translateY(0)}}20%{{opacity:1}}"
                   f"100%{{opacity:0;transform:translateY({f2(-9 * s)}px)}}}}")
    if bubble:
        bx, by = x + 22 * s, y - 9 * s
        parts.append(sprite(BUBBLE, C, bx, by, s * 0.75))
        for i in range(3):
            parts.append(f'<rect class="{p}dot" x="{f2(bx + (3.2 + i * 2.8) * s * 0.75)}" '
                         f'y="{f2(by + 3.6 * s * 0.75)}" width="{f2(1.6 * s * 0.75)}" '
                         f'height="{f2(1.6 * s * 0.75)}" fill="#{t["overlay0"]}" '
                         f'style="animation-delay:{i * 0.25:.2f}s"/>')
        css.append(f".{p}dot{{animation:{p}dot 1.5s ease-in-out infinite}}"
                   f"@keyframes {p}dot{{0%,60%,100%{{opacity:.25}}30%{{opacity:1}}}}")
    return "".join(parts), "".join(css)


def walker_frames_css(p, period=0.3):
    return cycle_css(f"{p}w", 2, period)


# --------------------------------------------------------------------------------------
# Static widgets: banner, divider, footer, pet
# --------------------------------------------------------------------------------------
def render_banner(cfg, t, C):
    W, H = 1000, 300
    css = [PULSE_CSS]
    defs = (f'<radialGradient id="glowA" cx="82%" cy="8%" r="55%"><stop offset="0" stop-color="#{t["mauve"]}" '
            f'stop-opacity=".26"/><stop offset="1" stop-color="#{t["mauve"]}" stop-opacity="0"/></radialGradient>'
            f'<radialGradient id="glowB" cx="6%" cy="100%" r="50%"><stop offset="0" stop-color="#{t["peach"]}" '
            f'stop-opacity=".16"/><stop offset="1" stop-color="#{t["peach"]}" stop-opacity="0"/></radialGradient>'
            f'<linearGradient id="nameGrad" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="#{t["mauve"]}"/>'
            f'<stop offset=".55" stop-color="#{t["pink"]}"/><stop offset="1" stop-color="#{t["peach"]}"/></linearGradient>'
            f'<pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse">'
            f'<circle cx="2" cy="2" r="1.2" fill="#{t["surface0"]}"/></pattern>'
            f'<clipPath id="cardClip"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="22"/></clipPath>')
    b = [card(W, H, t, 22),
         f'<g clip-path="url(#cardClip)"><rect width="{W}" height="{H}" fill="url(#dots)" opacity=".7"/>'
         f'<rect width="{W}" height="{H}" fill="url(#glowA)"/><rect width="{W}" height="{H}" fill="url(#glowB)"/></g>']
    # window chrome
    for i, col in enumerate(("red", "yellow", "green")):
        b.append(f'<circle cx="{32 + i * 20}" cy="30" r="6" fill="#{t[col]}"/>')
    if cfg.get("terminal_title"):
        b.append(text(100, 35, cfg["terminal_title"], 13, t["overlay1"], 500, MONO))
    if cfg.get("status_pill"):
        label = cfg["status_pill"]
        pw = text_w(label, 12, True) + 34
        frag, _ = pill(W - 26 - pw, 18, label, t["green"], t, 12)
        b.append(frag)
    # prompt
    path, cmd = cfg.get("prompt_path", "~"), "whoami"
    b.append(f'<text x="48" y="96" font-family="{MONO}" font-size="18" font-weight="600">'
             f'<tspan fill="#{t["green"]}">{esc(path)}</tspan><tspan fill="#{t["overlay1"]}"> $ </tspan>'
             f'<tspan fill="#{t["text"]}">{cmd}</tspan></text>')
    cur_x = 48 + text_w(f"{path} $ {cmd}", 18, True) + 6
    b.append(f'<rect class="cursor" x="{f2(cur_x)}" y="81" width="10" height="19" fill="#{t["text"]}"/>')
    css.append(".cursor{animation:cur 1.1s step-end infinite}@keyframes cur{0%,100%{opacity:1}50%{opacity:0}}")
    # name + lines
    name = cfg.get("name", "")
    size = 56 if text_w(name, 56) < 540 else max(34, 56 * 540 / text_w(name, 56))
    b.append(f'<text x="46" y="158" font-family="{SANS}" font-size="{f2(size)}" font-weight="800" '
             f'letter-spacing="-1" fill="url(#nameGrad)">{esc(name)}</text>')
    head = cfg.get("headline", "")
    hsize = 22 if text_w(head, 22) <= 540 else max(15, 22 * 540 / text_w(head, 22))
    b.append(text(48, 200, head, hsize, t["subtext1"], 600))
    if cfg.get("subline"):
        sub = cfg["subline"]
        ssize = 17 if text_w(sub, 17) <= 540 else max(12, 17 * 540 / text_w(sub, 17))
        b.append(text(48, 230, sub, ssize, t["overlay2"], 500))
    # chips
    cx = 48
    palette = ["mauve", "peach", "green", "sky", "pink", "yellow", "lavender", "teal"]
    for i, chip in enumerate(cfg.get("chips", [])[:7]):
        w = text_w(chip, 13, True) + 34
        if cx + w > 600:
            break
        col = t[palette[i % len(palette)]]
        b.append(f'<rect x="{f2(cx)}" y="250" width="{f2(w)}" height="28" rx="14" fill="#{t["surface0"]}" '
                 f'stroke="#{t["surface1"]}"/><circle cx="{f2(cx + 15)}" cy="264" r="4.5" fill="#{col}"/>')
        b.append(text(cx + 26, 268.5, chip, 13, t["text"], 600, MONO))
        cx += w + 10
    # the cat
    sx, sy, s = 640, 50, 5
    b.append(f'<ellipse cx="{sx + 150}" cy="{sy + 228}" rx="150" ry="7" fill="#{t["crust"]}" opacity=".55"/>')
    scene, scss = laptop_scene(sx, sy, s, C, t, "lp")
    b.append(scene)
    css.append(scss)
    # floating code glyphs
    glyphs = [("{ }", "mauve", 618, 150), ("</>", "peach", 968, 178), ("=>", "green", 622, 236),
              (";", "sky", 970, 250), ("0x1F", "pink", 922, 120), ("( )", "yellow", 628, 100)]
    for i, (g, col, gx, gy) in enumerate(glyphs):
        b.append(text(gx, gy, g, 15, t[col], 700, MONO, "middle",
                      extra=f' class="gl" style="animation-delay:-{i * 1.1:.1f}s"'))
    css.append(".gl{opacity:0;animation:gl 6.6s ease-in-out infinite}"
               "@keyframes gl{0%{opacity:0;transform:translateY(12px)}20%{opacity:.85}"
               "75%{opacity:.6}100%{opacity:0;transform:translateY(-46px)}}")
    title = f"{name} - {cfg.get('headline', '')}"
    desc = "Animated banner: a pixel-art cat peeking over a laptop and typing code."
    return svg_doc(W, H, "".join(b), "".join(css), title, desc, defs)


def render_divider(cfg, t, C):
    W, H = 1000, 56
    b, css = [], []
    b.append(f'<line x1="16" y1="47" x2="{W - 16}" y2="47" stroke="#{t["surface1"]}" stroke-width="2" '
             f'stroke-linecap="round" stroke-dasharray="2 9"/>')
    period, start_x, end_x = 16.0, -60, W + 10
    speed = (end_x - start_x) / period
    for i, px in enumerate(range(70, W - 40, 72)):
        delay = (px - 30 - start_x) / speed
        b.append(sprite(PAW, C, px, 41, 1.6, "pp", f' style="animation-delay:{delay:.2f}s"'))
    css.append(".pp{opacity:0;animation:pp 16s linear infinite}"
               "@keyframes pp{0%{opacity:0}1.5%{opacity:.75}30%{opacity:0}100%{opacity:0}}")
    frames = "".join(sprite(walker(f), C, 0, 0, 2, f"dvw{i}") for i, f in enumerate("AB"))
    b.append(f'<g class="walk">{frames}</g>')
    css.append(walker_frames_css("dv", 0.32))
    css.append(f".walk{{transform:translate({W // 2 - 24}px,17px);animation:walk {f2(period)}s linear infinite}}"
               f"@keyframes walk{{from{{transform:translate({start_x}px,17px)}}to{{transform:translate({end_x}px,17px)}}}}")
    return svg_doc(W, H, "".join(b), "".join(css), "Section divider",
                   "A small pixel cat walks across a dotted line, leaving paw prints.")


def render_footer(cfg, t, C):
    W, H = 1000, 210
    f = cfg["footer"]
    b, css = [card(W, H, t, 22)], []
    rnd = random.Random(7)
    for i in range(40):
        sx, sy = rnd.uniform(24, W - 24), rnd.uniform(18, H - 24)
        if (50 < sx < 300 and sy > 60) or (315 < sx < 880 and 55 < sy < 190):
            continue  # keep stars away from the cat and the text
        r = rnd.choice((1, 1.2, 1.6))
        b.append(f'<circle class="tw" cx="{f2(sx)}" cy="{f2(sy)}" r="{r}" fill="#{t["text"]}" '
                 f'style="animation-delay:-{rnd.uniform(0, 4):.1f}s"/>')
    css.append(".tw{opacity:.15;animation:tw 4s ease-in-out infinite}"
               "@keyframes tw{0%,100%{opacity:.12}50%{opacity:.85}}")
    # moon
    b.append(f'<defs><mask id="moonMask"><rect width="{W}" height="{H}" fill="#fff"/>'
             f'<circle cx="{W - 88}" cy="52" r="22" fill="#000"/></mask></defs>'
             f'<circle cx="{W - 100}" cy="62" r="26" fill="#{t["yellow"]}" mask="url(#moonMask)"/>')
    # closed laptop as a bed
    lx, ly = 70, 160
    b.append(f'<rect x="{lx}" y="{ly}" width="190" height="12" rx="4" fill="#{t["surface2"]}"/>'
             f'<rect x="{lx + 6}" y="{ly + 12}" width="178" height="5" rx="2" fill="#{t["surface1"]}"/>'
             f'<circle class="led" cx="{lx + 178}" cy="{ly + 6}" r="2.2" fill="#{t["green"]}"/>')
    css.append(".led{animation:led 3.2s ease-in-out infinite}@keyframes led{0%,100%{opacity:.15}50%{opacity:1}}")
    scene, scss = sleeper_scene(lx + 18, ly - 74, 5, C, t, "sl")
    b.append(scene)
    css.append(scss)
    # text
    tx = 330
    b.append(text(tx, 92, f["title"], 30, t["text"], 800))
    for i, line in enumerate(wrap_px(f.get("subtitle", ""), 17, 540)[:2]):
        b.append(text(tx, 124 + i * 22, line, 17, t["subtext0"], 500))
    cmd = f.get("command", "")
    if cmd:
        b.append(f'<text x="{tx}" y="176" font-family="{MONO}" font-size="15" font-weight="600">'
                 f'<tspan fill="#{t["green"]}">$ </tspan><tspan fill="#{t["text"]}">{esc(cmd)}</tspan></text>')
        cx = tx + text_w("$ " + cmd, 15, True) + 5
        b.append(f'<rect class="cursor" x="{f2(cx)}" y="163" width="8" height="16" fill="#{t["text"]}"/>')
        css.append(".cursor{animation:cur 1.1s step-end infinite}@keyframes cur{0%,100%{opacity:1}50%{opacity:0}}")
    return svg_doc(W, H, "".join(b), "".join(css), f["title"],
                   "A pixel cat sleeps on a closed laptop under a crescent moon.")


def render_pet(cfg, t, C):
    W, H = 760, 230
    p = cfg["pet"]
    b, css = [card(W, H, t, 18)], []
    scene, scss = sit_scene(46, 22, 5.6, C, t, "pt", eyes="happy", hearts=True)
    b.append(scene)
    css.append(scss)
    b.append(text(300, 98, p["title"], 34, t["mauve"], 800, extra=' class="purr"'))
    css.append(".purr{animation:purr .18s linear infinite}"
               "@keyframes purr{0%,100%{transform:translate(0,0)}50%{transform:translate(1px,-1px)}}")
    b.append(text(300, 140, p["subtitle"], 20, t["text"], 600))
    b.append(text(300, 178, p["footnote"], 14, t["overlay1"], 500, MONO))
    return svg_doc(W, H, "".join(b), "".join(css), "You pet the cat",
                   "A pixel cat purrs happily with hearts floating above its head.")


# --------------------------------------------------------------------------------------
# Data-driven widgets: status, oracle, streak, activity
# --------------------------------------------------------------------------------------
MOODS = {
    "roll": ("ON A ROLL", "peach", "On a roll!", [
        "Paws moving faster than the build server.", "Streak so hot the keyboard is warm.",
        "Zoomies, but make them productive.", "Shipping like there is tuna at the finish line."]),
    "coding": ("CODING", "green", "Coding mode: on", [
        "Tapping keys, chasing bugs.", "Currently knocking bugs off the table.",
        "Deep focus. Please do not pet.", "Turning coffee and curiosity into commits."]),
    "napping": ("NAPPING", "lavender", "Taking a cat nap", [
        "Recharging. Probably building something offline.", "Dreaming in Dart and Python.",
        "Busy elsewhere, most likely inside a box.", "Garbage-collecting the brain."]),
    "daydream": ("DAYDREAMING", "sky", "Plotting new ideas", [
        "Thinking in boxes and arrows.", "Sketching ideas on the back of a napkin.",
        "Somewhere between an idea and a commit.", "Waiting for the next spark."]),
    "snack": ("SNACK TIME", "pink", "Snack time!", [
        "A kind visitor brought fish. Purring loudly.", "Nom nom nom. Thank you, human.",
        "Fed, happy, and ready to code again."]),
    "warmup": ("WARMING UP", "overlay2", "Warming up...", [
        "Run the workflow once to wake the cat.", "Stats arrive after the first workflow run."]),
}


def pick_mood(cfg, stats, state, now_utc):
    m = cfg["moods"]
    last_fed = parse_iso(state.get("last_fed_at")) if state else None
    if last_fed and (now_utc - last_fed).total_seconds() < m["snack_hours"] * 3600:
        return "snack"
    if not stats:
        return "warmup"
    if not stats.get("last_active"):
        return "daydream"
    today = dt.date.fromisoformat(stats["today"])
    since = (today - dt.date.fromisoformat(stats["last_active"])).days
    if stats["current_streak"]["len"] >= m["on_a_roll_streak"] or stats["week_total"] >= m["on_a_roll_week"]:
        return "roll"
    if since <= m["coding_days"]:
        return "coding"
    if since <= m["napping_days"]:
        return "napping"
    return "daydream"


def fmt_day(d: dt.date) -> str:
    return f"{d.day} {d.strftime('%b')}"


def render_status(cfg, t, C, data, state, now_utc):
    W, H = 480, 252
    stats = (data or {}).get("stats")
    mood = pick_mood(cfg, stats, state, now_utc)
    label, color_key, headline, quips = MOODS[mood]
    color = t[color_key]
    local_now = to_local(now_utc, cfg)
    quip = random.Random(f"{local_now.date()}-{mood}").choice(quips)
    b, css = [card(W, H, t, 16)], [PULSE_CSS]
    cat_name = cfg["cat"].get("name", "Miao")
    b.append(sprite(PAW, C, 22, 19, 2.4))
    b.append(text(42, 31, f"{cat_name.upper()}.STATUS", 12, t["overlay1"], 700, MONO,
                  extra=' letter-spacing="1.5"'))
    pw = text_w(label, 11.5, True) + 34
    frag, _ = pill(W - 20 - pw, 13, label, color, t)
    b.append(frag)
    b.append(f'<line x1="18" y1="48" x2="{W - 18}" y2="48" stroke="#{t["surface0"]}" stroke-width="1.5"/>')
    # pose
    if mood in ("roll", "coding"):
        frag, scss = laptop_scene(20, 82, 3, C, t, "lp", 0.24 if mood == "roll" else 0.36, mood == "roll")
    elif mood == "napping":
        frag, scss = sleeper_scene(28, 138, 5, C, t, "sl")
    elif mood == "snack":
        frag, scss = sit_scene(38, 90, 4, C, t, "st", "happy", "bowl_full", hearts=True)
    else:
        frag, scss = sit_scene(38, 90, 4, C, t, "st", "open", "bowl_empty", bubble=mood != "warmup")
    b.append(frag)
    css.append(scss)
    # text column
    tx = 214
    hsize = 19 if text_w(headline, 19) <= 240 else max(14, 19 * 240 / text_w(headline, 19))
    b.append(text(tx, 82, headline, hsize, t["text"], 800))
    for i, line in enumerate(wrap_px(quip, 13, 240)[:2]):
        b.append(text(tx, 106 + i * 17, line, 13, t["subtext0"], 500))
    rows_y = 152
    fish = int(state.get("fish", 0)) if state else 0
    humans = len(state.get("feeders", {})) if state else 0
    if stats:
        week, streak = stats["week_total"], stats["current_streak"]["len"]
        week_val = f"{week}"
        streak_val = f"{streak} day{'s' if streak != 1 else ''}"
    else:
        week_val = streak_val = "--"
    last = state.get("last_feeder") if state else None
    last_val = "nobody yet!"
    if last:
        when = parse_iso(state.get("last_fed_at"))
        last_val = f"@{clip_text(last, 11)}" + (f" · {fmt_day(to_local(when, cfg).date())}" if when else "")
    fish_val = f"{fish}" + (f" · {humans} human{'s' if humans != 1 else ''}" if fish else " so far")
    rows = [("THIS WEEK", week_val, "cal"), ("STREAK", streak_val, "flame"),
            ("FISH EATEN", fish_val, "fish"), ("LAST SNACK", last_val, "heart")]
    vx = tx + 94
    for i, (lab, val, icon) in enumerate(rows):
        y = rows_y + i * 22
        if icon == "flame":
            b.append(sprite(FLAME, C, tx, y - 11.5, 1.55))
        elif icon == "fish":
            b.append(sprite(FISH, C, tx - 2, y - 10, 1.2))
        elif icon == "heart":
            b.append(sprite(HEART, C, tx, y - 9.5, 1.55))
        else:
            b.append(f'<rect x="{tx}" y="{y - 11}" width="11" height="11" rx="2" fill="none" '
                     f'stroke="#{t["sky"]}" stroke-width="1.6"/><rect x="{tx}" y="{y - 11}" width="11" '
                     f'height="3.2" rx="1" fill="#{t["sky"]}"/>')
        b.append(text(tx + 18, y, lab, 10.5, t["overlay1"], 700, MONO, extra=' letter-spacing=".6"'))
        b.append(text(vx, y, clip_text(val, 21), 13, t["text"], 700))
    if stats:  # sparkline of the last 7 days, right after the weekly number
        vals = stats["last7"]
        top = max(vals) or 1
        sx0 = vx + text_w(week_val, 13) + 10
        for i, v in enumerate(vals):
            h = 2 if v == 0 else 3 + 11 * v / top
            fillc = t["surface1"] if v == 0 else color
            b.append(f'<rect x="{f2(sx0 + i * 6)}" y="{f2(rows_y - h + 1)}" width="4" height="{f2(h)}" '
                     f'rx="1" fill="#{fillc}"/>')
        b.append(text(sx0 + 46, rows_y, "last 7 days", 10, t["overlay0"], 500, MONO))
    foot = (f"updated {local_now.strftime('%d %b %Y, %H:%M')} {cfg.get('timezone_label', '')}".strip()
            if stats or (state and state.get("fish")) else "waiting for the first workflow run")
    b.append(text(tx, H - 14, foot, 10.5, t["overlay0"], 500, MONO))
    desc = f"{cat_name} the cat is {label.lower()}: {headline}. {quip}"
    return svg_doc(W, H, "".join(b), "".join(css), f"{cat_name}'s live status", desc)


ORACLE_QUOTES = [
    "Small commits, often. Even a cat knocks things off the table one at a time.",
    "Naps are just garbage collection for the brain.",
    "Comment your code. Future you is a different, grumpier cat.",
    "If it works on the first try, check that you saved the file.",
    "Every senior developer was once a kitten chasing semicolons.",
    "Stare calmly at the merge conflict. It will blink first.",
    "Ship it, then purr over the feedback.",
    "Today's spaghetti is tomorrow's legacy system. Choose your noodles wisely.",
    "Curiosity did not kill the cat. It made it a better engineer.",
    "There is no cloud. It is just someone else's cardboard box.",
    "Rest is part of the sprint. Even the fastest cat sleeps sixteen hours a day.",
    "Read the error message. Then read it again, slower.",
    "A good variable name saves a thousand comments.",
    "No rubber duck? Explain it to the cat. The cat is unimpressed, but it works.",
    "Do not fear the blank file. Every great repo started as one.",
    "Measure twice, deploy once.",
    "Refactor like a cat grooms: a little bit, every single day.",
    "Your future self will run git blame. Leave them something nice to find.",
    "Shipping beats perfect. Perfect is a box you will never fit in.",
    "Learn the fundamentals. Frameworks come and go like the red dot.",
    "Version control is nine lives for your code.",
    "Optimise when it hurts, not when you are bored.",
    "Sleep on the hard bug. Your brain keeps debugging while you nap.",
    "A clean commit history is a well-groomed coat.",
    "The cat sees all your TODOs. The cat judges none of them. Mostly.",
    "Good documentation is a warm windowsill for the next developer.",
    "Delete code fearlessly. Git remembers, so you do not have to.",
    "Edge cases are the cat walking across your keyboard. Plan for them.",
    "Land on your feet: always keep a rollback plan.",
    "Keep functions small enough to fit in a cardboard box.",
    "Coffee compiles your thoughts. Naps link them.",
    "Tests are green? Stretch, yawn, and enjoy it. You earned it.",
    "Big features are made of tiny pull requests.",
    "Logs are breadcrumbs. Leave enough to find your way home.",
    "Every new dependency is a new cat in the house. Introduce it carefully.",
    "The red dot is not a requirement. Scope wisely.",
    "Today's experiment is tomorrow's portfolio project.",
    "Commit messages are notes to your future self. Make them purr-fectly clear.",
    "A stack trace is a treasure map. Start at the top and dig where it points.",
    "Automate the boring parts. Save your claws for the hard problems.",
    "Good UX is invisible, like a cat entering a room.",
    "Consistency beats intensity. One commit a day keeps the rust away.",
    "Break big problems into small kibble.",
    "Stuck? Step away from the keyboard. Cats never force it.",
    "Celebrate the green build, then refill the water bowl.",
    "Hydrate. Commit. Nap. Repeat.",
    "Leave the litter box cleaner than you found it. Same goes for the codebase.",
    "Simple code is hard to write and easy to love.",
    "A failing test is a friend who tells you the truth.",
    "Knock one bug off the table at a time.",
    "Ask the question. Silence turns small bugs into big ones.",
    "The best code review comment is a kind one.",
    "Name things as if a sleepy cat will read them at 3am.",
    "Pair programming: two cats, one keyboard, surprisingly few typos.",
    "When the build breaks, do not hiss. Read the logs.",
    "Ideas are cheap. Prototypes purr.",
]


def render_oracle(cfg, t, C, today: dt.date):
    W, H = 900, 180
    o = cfg["oracle"]
    quotes = (ORACLE_QUOTES if o.get("use_builtin_quotes", True) else []) + list(o.get("quotes") or [])
    quotes = [q for q in quotes if q.strip()] or ORACLE_QUOTES
    order = list(range(len(quotes)))
    random.Random(1312).shuffle(order)
    idx = order[today.toordinal() % len(quotes)]
    quote = quotes[idx]
    defs = (f'<radialGradient id="ballGlow"><stop offset="0" stop-color="#{t["lavender"]}" stop-opacity=".9"/>'
            f'<stop offset="1" stop-color="#{t["lavender"]}" stop-opacity="0"/></radialGradient>'
            f'<linearGradient id="wipe" x1="0" x2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0"/>'
            f'<stop offset=".5" stop-color="#FFFFFF" stop-opacity=".16"/><stop offset="1" stop-color="#FFFFFF" '
            f'stop-opacity="0"/></linearGradient>')
    b, css = [card(W, H, t, 18)], []
    s, cx, cy = 4, 30, 14
    ball_cx, ball_cy = cx + 14 * s, cy + 25 * s
    b.append(f'<circle class="glow" cx="{ball_cx}" cy="{ball_cy}" r="58" fill="url(#ballGlow)"/>')
    css.append(".glow{animation:glow 3.2s ease-in-out infinite}@keyframes glow{0%,100%{opacity:.35}50%{opacity:.85}}")
    scene, scss = sit_scene(cx, cy, s, C, t, "or", eyes="glow", prop="ball")
    b.append(scene)
    css.append(scss)
    for i, (dx, dy) in enumerate(((-6, 70), (128, 50), (120, 128), (2, 140))):
        b.append(sprite(SPARK, C, cx + dx, cy + dy, 2, "spk", f' style="animation-delay:-{i * 0.6:.1f}s"'))
    css.append(".spk{transform-box:fill-box;transform-origin:center;animation:spk 2.4s ease-in-out infinite}"
               "@keyframes spk{0%,100%{opacity:0;transform:scale(.3)}50%{opacity:1;transform:scale(1)}}")
    tx = 200
    b.append(text(tx, 46, o.get("title", "THE MIAORICLE SAYS"), 13, t["mauve"], 800, MONO,
                  extra=' letter-spacing="3"'))
    size = 21
    lines = wrap_px(f"“{quote}”", size, 620)
    if len(lines) > 2:
        size = 18
        lines = wrap_px(f"“{quote}”", size, 630)[:3]
    step = size + 9
    first = 104 + size * 0.35 - (len(lines) - 1) * step / 2
    wipes = []
    for i, line in enumerate(lines):
        y = first + i * step
        b.append(text(tx, y, line, size, t["text"], 650))
        wipes.append(y)
    top, bottom = wipes[0] - size - 6, wipes[-1] + 10
    b.append(f'<clipPath id="quoteClip"><rect x="{tx - 8}" y="0" width="{W - tx - 6}" height="{H}"/></clipPath>'
             f'<g clip-path="url(#quoteClip)"><rect class="wp" x="{tx - 120}" y="{f2(top)}" width="90" '
             f'height="{f2(bottom - top)}" fill="url(#wipe)"/></g>')
    css.append(f".wp{{opacity:0;animation:wp 2.4s ease-in-out .6s 2 both}}"
               f"@keyframes wp{{0%{{opacity:1;transform:translateX(0) skewX(-18deg)}}"
               f"100%{{opacity:1;transform:translateX({W - tx + 160}px) skewX(-18deg)}}}}")
    foot = f"— prophecy {idx + 1} of {len(quotes)} · {today.strftime('%A')}, {today.day} {today.strftime('%b %Y')}"
    b.append(text(tx, H - 22, foot, 12.5, t["overlay1"], 500, MONO))
    b.append(text(W - 24, H - 22, "a new one every day", 12.5, t["overlay0"], 500, MONO, "end"))
    return svg_doc(W, H, "".join(b), "".join(css), "The Miaoricle's prophecy of the day", quote, defs)


def render_streak(cfg, t, C, data):
    W, H = 820, 196
    stats = (data or {}).get("stats")
    b, css = [card(W, H, t, 16)], []
    cols = (W / 6, W / 2, 5 * W / 6)
    for xx in (W / 3, 2 * W / 3):
        b.append(f'<line x1="{f2(xx)}" y1="40" x2="{f2(xx)}" y2="{H - 40}" stroke="#{t["surface1"]}"/>')
    if stats:
        tot, cur, lon = stats["total_all_time"], stats["current_streak"], stats["longest_streak"]
        first = dt.date.fromisoformat(stats["first_date"]) if stats.get("first_date") else None
        tot_range = f"{first.strftime('%b %Y')} – Present" if first else "—"
        cur_range = _range(cur)
        lon_range = _range(lon)
        tot_v, cur_v, lon_v = f"{tot:,}", f"{cur['len']}", f"{lon['len']}"
    else:
        tot_v = cur_v = lon_v = "--"
        tot_range = cur_range = lon_range = "waiting for data"
    css.append(".num{animation:up .6s ease-out both}"
               "@keyframes up{from{opacity:.35;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}")
    # left + right columns
    for (xx, val, lab, rng, delay) in ((cols[0], tot_v, "Total Contributions", tot_range, 0.15),
                                       (cols[2], lon_v, "Longest Streak", lon_range, 0.45)):
        b.append(text(xx, 96, val, 32, t["text"], 800, anchor="middle",
                      extra=f' class="num" style="animation-delay:{delay}s"'))
        b.append(text(xx, 128, lab, 15, t["subtext1"], 600, anchor="middle"))
        b.append(text(xx, 152, rng, 12, t["overlay1"], 500, MONO, "middle"))
    # centre ring with the cat peeking over it
    rx, ry, r = cols[1], 92, 44
    circ = 2 * math.pi * r
    b.append(f'<circle cx="{f2(rx)}" cy="{ry}" r="{r}" fill="none" stroke="#{t["surface0"]}" stroke-width="7"/>')
    b.append(f'<circle class="ring" cx="{f2(rx)}" cy="{ry}" r="{r}" fill="none" stroke="#{t["mauve"]}" '
             f'stroke-width="7" stroke-linecap="round" stroke-dasharray="{f2(circ)}" '
             f'transform="rotate(-90 {f2(rx)} {ry})"/>')
    css.append(f".ring{{stroke-dashoffset:0;animation:ring 1.4s ease-out both}}"
               f"@keyframes ring{{from{{stroke-dashoffset:{f2(circ)}}}to{{stroke-dashoffset:0}}}}")
    asleep = bool(stats) and stats["current_streak"]["len"] == 0
    head = mini_eyes(MINI, "closed" if asleep else "open")
    hs = 3
    hx, hy = rx - 6 * hs, ry - r - 23
    b.append(f'<rect x="{f2(hx + 3)}" y="{f2(hy + 18)}" width="{f2(12 * hs - 6)}" height="14" fill="#{t["base"]}"/>')
    b.append(sprite(head, C, hx, hy, hs))
    if not asleep:
        b.append(sprite(diff(head, mini_eyes(MINI, "closed")), C, hx, hy, hs, "hb"))
        css.append(blink_css("hb", 4.4))
    b.append(text(rx, ry + 12, cur_v, 34, t["peach"], 800, anchor="middle",
                  extra=' class="num" style="animation-delay:.3s"'))
    b.append(text(rx, 160, "Current Streak", 15, t["peach"], 700, anchor="middle"))
    b.append(text(rx, 181, cur_range, 12, t["overlay1"], 500, MONO, "middle"))
    return svg_doc(W, H, "".join(b), "".join(css), "Contribution streak",
                   f"Total contributions {tot_v}, current streak {cur_v} days, longest streak {lon_v} days.")


def _range(st):
    if not st or not st.get("len"):
        return "—"
    a, z = dt.date.fromisoformat(st["start"]), dt.date.fromisoformat(st["end"])
    return fmt_day(a) if a == z else f"{fmt_day(a)} – {fmt_day(z)}"


def render_activity(cfg, t, C, data):
    W, H = 820, 218
    cal = (data or {}).get("calendar")
    stats = (data or {}).get("stats") or {}
    b, css = [card(W, H, t, 16)], []
    b.append(text(24, 32, "THE CONTRIBUTION CHASE", 12, t["overlay1"], 800, MONO, extra=' letter-spacing="2"'))
    if cal:
        weeks = cal["weeks"]
    else:  # no data yet: draw an empty year so the card still looks like a contribution graph
        end = utcnow().date()
        start = end - dt.timedelta(days=364 + end.isoweekday() % 7)
        days = [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]
        weeks = [[{"d": d.isoformat(), "c": 0} for d in days[i:i + 7]] for i in range(0, len(days), 7)]
    total = cal["total"] if cal else None
    right = (f"{total:,} contributions in the last year" if total is not None
             else "waiting for the first workflow run")
    b.append(text(W - 24, 32, right, 13, t["subtext0"], 600, anchor="end"))
    nweeks = len(weeks)
    pitch, cell = 14, 11
    gw = nweeks * pitch - (pitch - cell)
    gx, gy = (W - gw) / 2, 70
    # month labels
    last_month, last_x = None, -99
    for wi, week in enumerate(weeks):
        days = [d for d in week if d.get("d")]
        if not days:
            continue
        m = dt.date.fromisoformat(days[0]["d"]).strftime("%b")
        x = gx + wi * pitch
        if m != last_month and x - last_x > 34:
            b.append(text(x, gy - 10, m, 10.5, t["overlay0"], 600, MONO))
            last_month, last_x = m, x
        elif m != last_month:
            last_month = m
    # levels
    counts = sorted(d["c"] for w in weeks for d in w if d.get("c", 0) > 0)

    def level(c):
        if c <= 0:
            return 0
        if not counts or counts[-1] <= 4:
            return min(4, c)
        q = [counts[int(len(counts) * f)] for f in (0.25, 0.5, 0.75)]
        return 1 + sum(c > v for v in q)

    shades = [t["surface0"]] + [mix(t["surface0"], t["green"], f) for f in (0.38, 0.6, 0.8, 1.0)]
    period, walk_frac = 30.0, 0.86
    total_steps = 7 * (nweeks - 1) + 6

    def dist(r, c):
        return r * nweeks + (c if r % 2 == 0 else (nweeks - 1 - c))

    cells, kf = [], {}
    for wi, week in enumerate(weeks):
        for d in week:
            if not d.get("d"):
                continue
            row = (dt.date.fromisoformat(d["d"]).isoweekday()) % 7
            x, y = gx + wi * pitch, gy + row * pitch
            lv = level(d.get("c", 0))
            attrs = ""
            if lv > 0:  # an empty square sits underneath, so the grid stays whole once eaten
                cells.append(f'<rect x="{f2(x)}" y="{f2(y)}" width="{cell}" height="{cell}" rx="2.5" '
                             f'fill="#{shades[0]}"/>')
                eat = walk_frac * 100 * dist(row, wi) / total_steps
                key = f"{eat:.1f}"
                if key not in kf:
                    name = f"e{len(kf)}"
                    e = float(key)
                    refill = 95 + 3.5 * wi / max(1, nweeks - 1)
                    kf[key] = name
                    css.append(f"@keyframes {name}{{0%,{e:.2f}%{{transform:scale(1);opacity:1}}"
                               f"{e + 0.45:.2f}%,{refill:.2f}%{{transform:scale(0);opacity:0}}"
                               f"{min(100, refill + 1.2):.2f}%,100%{{transform:scale(1);opacity:1}}}}")
                attrs = f' class="cl" style="animation-name:{kf[key]}"'
            cells.append(f'<rect x="{f2(x)}" y="{f2(y)}" width="{cell}" height="{cell}" rx="2.5" '
                         f'fill="#{shades[lv]}"{attrs}/>')
    css.append(f".cl{{transform-box:fill-box;transform-origin:center;animation-duration:{f2(period)}s;"
               f"animation-timing-function:linear;animation-iteration-count:infinite}}")
    b.append("".join(cells))
    if cal and counts:
        # the cat walks the grid row by row (boustrophedon), eating every square it passes
        s = 1.5
        head_col = 17  # column of the walker's head centre (sprite faces right)
        dy = -15 * s + 3
        x_of = lambda c: gx + c * pitch + cell / 2
        y_of = lambda r: gy + r * pitch + cell / 2
        pts = []
        for r in range(7):
            for c in ((0, nweeks - 1) if r % 2 == 0 else (nweeks - 1, 0)):
                pts.append((dist(r, c), x_of(c), y_of(r)))
        pct = lambda d: walk_frac * 100 * d / total_steps
        pos_kf = "".join(f"{pct(d):.3f}%{{transform:translate({f2(x)}px,{f2(y)}px)}}" for d, x, y in pts)
        end_x, end_y = pts[-1][1], pts[-1][2]
        pos_kf += f"100%{{transform:translate({f2(end_x)}px,{f2(end_y)}px)}}"
        css.append(f"@keyframes chase{{{pos_kf}}}.chase{{transform:translate({f2(pts[0][1])}px,{f2(pts[0][2])}px);"
                   f"animation:chase {f2(period)}s linear infinite}}")
        # which way the cat faces: right on even rows, left on odd rows, hidden while resting
        for side, even in (("fr", True), ("fl", False)):
            kf = []
            for r in range(7):
                kf.append(f"{pct(r * nweeks):.3f}%{{opacity:{1 if (r % 2 == 0) == even else 0}}}")
            kf.append(f"{walk_frac * 100:.3f}%{{opacity:0}}100%{{opacity:0}}")
            css.append(f"@keyframes {side}{{{''.join(kf)}}}.{side}{{opacity:{1 if even else 0};"
                       f"animation:{side} {f2(period)}s step-end infinite}}")
        css.append(f"@keyframes resting{{0%,{walk_frac * 100:.2f}%{{opacity:0}}"
                   f"{walk_frac * 100 + 0.01:.2f}%,99.9%{{opacity:1}}100%{{opacity:0}}}}"
                   f".resting{{opacity:0;animation:resting {f2(period)}s step-end infinite}}")
        right = "".join(sprite(walker(f), C, -head_col * s, dy, s, f"acw{i}") for i, f in enumerate("AB"))
        left = "".join(sprite([r[::-1] for r in walker(f)], C, -(23 - head_col) * s, dy, s, f"acw{i}")
                       for i, f in enumerate("AB"))
        css.append(walker_frames_css("ac", 0.24))
        b.append(f'<g class="chase"><g class="fr">{right}</g><g class="fl">{left}</g></g>')
        b.append(f'<g class="resting">{sprite(walker("A", "happy"), C, end_x - head_col * s, end_y + dy, s)}'
                 f'{sprite(HEART, C, end_x - 6, end_y - 34, 1.6, "rh")}</g>')
        css.append(".rh{animation:rh 1.2s ease-in-out infinite}"
                   "@keyframes rh{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}")
    if not cal:
        frag, scss = sleeper_scene(W / 2 - 62, gy + 18, 4, C, t, "sl")
        b.append(f'<rect x="{f2(W / 2 - 90)}" y="{gy + 4}" width="180" height="86" rx="12" fill="#{t["base"]}" opacity=".88"/>')
        b.append(frag)
        css.append(scss)
    # footer: legend + facts
    ly = H - 22
    lx = W - 24 - 5 * 15 - 70
    b.append(text(lx - 6, ly, "less", 11, t["overlay0"], 600, MONO, "end"))
    for i, sh in enumerate(shades):
        b.append(f'<rect x="{f2(lx + i * 15)}" y="{ly - 10}" width="11" height="11" rx="2.5" fill="#{sh}"/>')
    b.append(text(lx + 5 * 15 + 4, ly, "more", 11, t["overlay0"], 600, MONO))
    if stats:
        facts = []
        if stats.get("best_day") and stats["best_day"]["count"]:
            bd = stats["best_day"]
            facts.append(f"best day {bd['count']} · {fmt_day(dt.date.fromisoformat(bd['date']))}")
        if stats.get("busiest_weekday"):
            facts.append(f"favourite day: {stats['busiest_weekday']}")
        facts.append("the cat eats every square, then naps")
        b.append(text(24, ly, "   ·   ".join(facts), 11, t["overlay1"], 600, MONO))
    return svg_doc(W, H, "".join(b), "".join(css), "The contribution chase",
                   "A pixel cat walks across the contribution graph and eats every active day.")


def render_placeholder(kind, t, C):
    W, H = (480, 195) if kind == "stats" else (320, 195)
    b, css = [card(W, H, t, 14)], []
    scene, scss = sleeper_scene(W / 2 - 62, 74, 4, C, t, "sl")
    b.append(scene)
    css.append(scss)
    b.append(text(W / 2, 156, "Waiting for the first workflow run", 13, t["subtext0"], 700, anchor="middle"))
    b.append(text(W / 2, 176, "Actions → Update profile widgets → Run", 11, t["overlay1"], 500, MONO, "middle"))
    return svg_doc(W, H, "".join(b), "".join(css), "Card not generated yet",
                   "Placeholder shown until the GitHub Action generates this card.")


# --------------------------------------------------------------------------------------
# Data: GitHub GraphQL
# --------------------------------------------------------------------------------------
GQL_CAL = """query($login:String!){user(login:$login){createdAt contributionsCollection{contributionYears
contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}"""
GQL_YEAR = """query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){
contributionsCollection(from:$from,to:$to){contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""


def gql(query, variables, token):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, method="POST", headers={
        "Authorization": f"bearer {token}", "Content-Type": "application/json",
        "User-Agent": "cat-widgets (github profile readme)"})
    with urllib.request.urlopen(req, timeout=40) as resp:
        payload = json.loads(resp.read().decode())
    if payload.get("errors"):
        raise RuntimeError("; ".join(e.get("message", "?") for e in payload["errors"]))
    if not payload.get("data", {}).get("user"):
        raise RuntimeError(f"user {variables.get('login')!r} not found")
    return payload["data"]["user"]


def fetch_data(login, token, now_utc):
    user = gql(GQL_CAL, {"login": login}, token)
    coll = user["contributionsCollection"]
    calendar = coll["contributionCalendar"]
    weeks = [[{"d": d["date"], "c": d["contributionCount"]} for d in w["contributionDays"]]
             for w in calendar["weeks"]]
    days = {d["d"]: d["c"] for w in weeks for d in w}
    for year in sorted(set(coll.get("contributionYears") or [])):
        start = dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc)
        end = min(dt.datetime(year, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc), now_utc)
        if end <= start:
            continue
        try:
            yu = gql(GQL_YEAR, {"login": login, "from": start.isoformat().replace("+00:00", "Z"),
                                "to": end.isoformat().replace("+00:00", "Z")}, token)
        except Exception as exc:  # keep going with what we have
            print(f"::warning::could not fetch {year}: {exc}")
            continue
        for w in yu["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                days.setdefault(d["date"], d["contributionCount"])
    return build_data(login, weeks, calendar["totalContributions"], days, now_utc)


def build_data(login, weeks, total_last_year, days, now_utc):
    today = max(d["d"] for w in weeks for d in w)
    return {"generated_at": now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "login": login, "calendar": {"total": total_last_year, "weeks": weeks},
            "stats": summarize(days, weeks, today)}


def summarize(days: dict, weeks, today_s: str) -> dict:
    today = dt.date.fromisoformat(today_s)
    ordered = sorted((dt.date.fromisoformat(k), v) for k, v in days.items() if k <= today_s)
    total = sum(v for _, v in ordered)
    first = next((d for d, v in ordered if v > 0), None)
    last = next((d for d, v in reversed(ordered) if v > 0), None)
    longest = {"len": 0, "start": None, "end": None}
    run_len, run_start, prev = 0, None, None
    for d, v in ordered:
        if v > 0:
            if run_len and prev and (d - prev).days == 1:
                run_len += 1
            else:
                run_len, run_start = 1, d
            if run_len > longest["len"]:
                longest = {"len": run_len, "start": run_start.isoformat(), "end": d.isoformat()}
        else:
            run_len = 0
        prev = d
    lookup = dict(ordered)
    day = today if lookup.get(today, 0) > 0 else today - dt.timedelta(days=1)
    cur_len, cur_end = 0, day
    while lookup.get(day, 0) > 0:
        cur_len += 1
        day -= dt.timedelta(days=1)
    current = {"len": cur_len, "start": (day + dt.timedelta(days=1)).isoformat() if cur_len else None,
               "end": cur_end.isoformat() if cur_len else None}
    last7 = [lookup.get(today - dt.timedelta(days=i), 0) for i in range(6, -1, -1)]
    year_days = [(dt.date.fromisoformat(d["d"]), d["c"]) for w in weeks for d in w]
    best = max(year_days, key=lambda x: (x[1], x[0])) if year_days else None
    per_wd = [0] * 7
    for d, v in year_days:
        per_wd[d.weekday()] += v
    busiest = None
    if any(per_wd):
        busiest = ["Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays", "Sundays"][
            per_wd.index(max(per_wd))]
    return {"today": today.isoformat(), "total_all_time": total,
            "first_date": first.isoformat() if first else None,
            "last_active": last.isoformat() if last else None,
            "current_streak": current, "longest_streak": longest, "last7": last7,
            "week_total": sum(last7),
            "best_day": {"date": best[0].isoformat(), "count": best[1]} if best else None,
            "busiest_weekday": busiest}


# --------------------------------------------------------------------------------------
# State, time and IO helpers
# --------------------------------------------------------------------------------------
def parse_iso(s):
    if not s:
        return None
    return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def to_local(when_utc, cfg):
    try:
        from zoneinfo import ZoneInfo
        return when_utc.astimezone(ZoneInfo(cfg.get("timezone") or "UTC"))
    except Exception:
        return when_utc


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_text(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def write_json(path, obj):
    write_text(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


# --------------------------------------------------------------------------------------
# Rendering entry points
# --------------------------------------------------------------------------------------
def render_static(cfg, out):
    t, C = get_theme(cfg), sprite_colors(cfg, get_theme(cfg))
    write_text(out / "banner.svg", render_banner(cfg, t, C))
    write_text(out / "divider.svg", render_divider(cfg, t, C))
    write_text(out / "footer.svg", render_footer(cfg, t, C))
    write_text(out / "pet.svg", render_pet(cfg, t, C))
    for kind in ("stats", "top-langs"):
        if not (out / f"{kind}.svg").exists():
            write_text(out / f"{kind}.svg", render_placeholder(kind, t, C))


def render_dynamic(cfg, out, data, state, now_utc):
    t, C = get_theme(cfg), sprite_colors(cfg, get_theme(cfg))
    write_text(out / "cat-status.svg", render_status(cfg, t, C, data, state, now_utc))
    write_text(out / "oracle.svg", render_oracle(cfg, t, C, to_local(now_utc, cfg).date()))
    write_text(out / "streak.svg", render_streak(cfg, t, C, data))
    write_text(out / "activity.svg", render_activity(cfg, t, C, data))


def cmd_update(args):
    cfg = load_config()
    out = OUT_DIR
    now = utcnow()
    login = cfg["github_username"]
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    data = read_json(out / "cat-data.json", None)
    if not login:
        print("::warning::No github_username in cat.config.json and no GITHUB_REPOSITORY_OWNER; skipping fetch")
    elif not token:
        print("::warning::No GITHUB_TOKEN available; rendering from cached data")
    else:
        try:
            data = fetch_data(login, token, now)
            write_json(out / "cat-data.json", data)
            s = data["stats"]
            print(f"Fetched {login}: {data['calendar']['total']} contributions last year, "
                  f"current streak {s['current_streak']['len']}, longest {s['longest_streak']['len']}")
        except (urllib.error.URLError, RuntimeError, KeyError, ValueError) as exc:
            print(f"::warning::Could not fetch contribution data ({exc}); using cached data")
    state = read_json(out / "cat-state.json", {"fish": 0, "feeders": {}})
    render_static(cfg, out)
    render_dynamic(cfg, out, data, state, now)
    print("Rendered widgets into", out)


def cmd_render(args):
    cfg = load_config()
    out = OUT_DIR
    data = read_json(out / "cat-data.json", None)
    state = read_json(out / "cat-state.json", {"fish": 0, "feeders": {}})
    render_static(cfg, out)
    render_dynamic(cfg, out, data, state, utcnow())
    print("Rendered widgets into", out)


def cmd_feed(args):
    cfg = load_config()
    out = OUT_DIR
    now = utcnow()
    feeder = (args.feeder or "").strip().lstrip("@")
    state = read_json(out / "cat-state.json", {"fish": 0, "feeders": {}})
    state.setdefault("fish", 0)
    state.setdefault("feeders", {})
    cat = cfg["cat"].get("name", "Miao")
    hours = float(cfg["feed"].get("cooldown_hours", 12))
    owner = cfg["github_username"]
    if not feeder or feeder.endswith("[bot]"):
        reply = "🤖 Bots can't feed the cat, sorry! Closing this one."
        status = "ignored"
    else:
        rec = state["feeders"].get(feeder, {})
        last = parse_iso(rec.get("last"))
        if last and (now - last).total_seconds() < hours * 3600:
            wait = hours - (now - last).total_seconds() / 3600
            reply = (f"😼 {cat} is still digesting your last fish, @{feeder}! "
                     f"Try again in about {max(1, math.ceil(wait))} hour{'s' if math.ceil(wait) != 1 else ''}. "
                     f"Closing this one. 🐾")
            status = "full"
        else:
            state["fish"] = int(state["fish"]) + 1
            state["feeders"][feeder] = {"n": int(rec.get("n", 0)) + 1,
                                        "last": now.replace(microsecond=0).isoformat().replace("+00:00", "Z")}
            state["last_feeder"] = feeder
            state["last_fed_at"] = state["feeders"][feeder]["last"]
            n_humans = len(state["feeders"])
            mine = state["feeders"][feeder]["n"]
            extra = "your first fish" if mine == 1 else f"fish number {mine} from you"
            reply = (f"🐟 **Nom nom nom!** Thank you @{feeder}, that was {extra}.\n\n"
                     f"{cat} has now eaten **{state['fish']}** fish from **{n_humans}** kind "
                     f"human{'s' if n_humans != 1 else ''}. The status card on "
                     f"[@{owner}'s profile](https://github.com/{owner}) will show it in a few minutes.\n\n"
                     f"You can feed {cat} again in {f2(hours)} hours. Closing this issue. 🐾")
            status = "fed"
    if status == "fed":  # only a real feeding changes anything on disk
        write_json(out / "cat-state.json", state)
        data = read_json(out / "cat-data.json", None)
        t, C = get_theme(cfg), sprite_colors(cfg, get_theme(cfg))
        write_text(out / "cat-status.svg", render_status(cfg, t, C, data, state, now))
    if args.result:
        write_text(args.result, reply + "\n")
    print(f"feed: {status} ({feeder or 'unknown'}), fish={state.get('fish', 0)}")


def cmd_card_options(args):
    cfg = load_config()
    t = get_theme(cfg)
    login = cfg["github_username"]
    c = cfg["cards"]
    common = {"bg_color": t["base"], "title_color": t["mauve"], "text_color": t["text"],
              "icon_color": t["peach"], "border_color": t["surface0"], "border_radius": "14"}
    stats = {"username": login, "show_icons": "true", "include_all_commits": "true",
             "count_private": "true", "rank_icon": "github", "ring_color": t["mauve"],
             "card_width": "480", **common}
    if c.get("stats_title"):
        stats["custom_title"] = c["stats_title"]
    langs = {"username": login, "layout": "compact", "langs_count": str(c.get("langs_count", 8)),
             "card_width": "320", "custom_title": c.get("langs_title", "Most Used Languages"), **common}
    exclude = [r for r in c.get("exclude_repos", []) if r]
    if exclude:
        langs["exclude_repo"] = ",".join(exclude)
    waka_user = os.environ.get("WAKATIME_USERNAME", "")
    waka = {"username": waka_user, "layout": "compact", "langs_count": "6",
            "custom_title": c.get("wakatime_title", "This Week in My Editor"), **common}
    lines = []
    for key, opts in (("stats", stats), ("langs", langs), ("wakatime", waka)):
        lines.append(f"{key}=" + urllib.parse.urlencode(opts, quote_via=urllib.parse.quote))
    text_out = "\n".join(lines) + "\n"
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write(text_out)
    print(text_out, end="")


def demo_data(now_utc):
    rnd = random.Random(42)
    today = to_local(now_utc, {"timezone": "UTC"}).date()
    start = today - dt.timedelta(days=364 + (today.isoweekday() % 7))
    weeks, week, days = [], [], {}
    d = start
    while d <= today:
        busy = 0.55 if d.weekday() < 5 else 0.3
        c = 0 if rnd.random() > busy else rnd.choice([1, 1, 2, 3, 4, 5, 6, 8, 12])
        if (today - d).days < 6:
            c = rnd.choice([2, 3, 5])
        week.append({"d": d.isoformat(), "c": c})
        days[d.isoformat()] = c
        if len(week) == 7:
            weeks.append(week)
            week = []
        d += dt.timedelta(days=1)
    if week:
        weeks.append(week)
    older = start - dt.timedelta(days=500)
    d = older
    while d < start:
        days[d.isoformat()] = 0 if rnd.random() > 0.35 else rnd.randint(1, 5)
        d += dt.timedelta(days=1)
    total = sum(x["c"] for w in weeks for x in w)
    return build_data("demo", weeks, total, days, now_utc)


def cmd_demo(args):
    cfg = load_config()
    out = Path(args.out)
    now = utcnow()
    data = demo_data(now)
    state = {"fish": 42, "feeders": {f"user{i}": {"n": 1, "last": "2026-01-01T00:00:00Z"} for i in range(17)},
             "last_feeder": "octocat", "last_fed_at": (now - dt.timedelta(days=2)).isoformat()}
    render_static(cfg, out)
    render_dynamic(cfg, out, data, state, now)
    t, C = get_theme(cfg), sprite_colors(cfg, get_theme(cfg))
    for mood_state, name in ((None, "warmup"), ({"fish": 3, "feeders": {"a": {}},
                                                 "last_fed_at": now.isoformat(), "last_feeder": "octocat"}, "snack")):
        write_text(out / f"status-{name}.svg",
                   render_status(cfg, t, C, None if name == "warmup" else data, mood_state or {}, now))
    for mood, last_active_days in (("coding", 1), ("napping", 6), ("daydream", 30)):
        d2 = json.loads(json.dumps(data))
        s = d2["stats"]
        s["last_active"] = (dt.date.fromisoformat(s["today"]) - dt.timedelta(days=last_active_days)).isoformat()
        s["current_streak"] = {"len": 0 if last_active_days > 1 else 2, "start": None, "end": None}
        s["week_total"] = 3 if mood == "coding" else 0
        write_text(out / f"status-{mood}.svg", render_status(cfg, t, C, d2, {"fish": 0, "feeders": {}}, now))
    print("Demo widgets written to", out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("update").set_defaults(fn=cmd_update)
    sub.add_parser("render").set_defaults(fn=cmd_render)
    f = sub.add_parser("feed")
    f.add_argument("--feeder", required=True)
    f.add_argument("--result", help="write the reply comment (markdown) to this file")
    f.set_defaults(fn=cmd_feed)
    sub.add_parser("card-options").set_defaults(fn=cmd_card_options)
    d = sub.add_parser("demo")
    d.add_argument("--out", default=str(ROOT / "demo-preview"))
    d.set_defaults(fn=cmd_demo)
    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
