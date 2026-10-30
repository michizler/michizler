"""Builds the profile README's SVG graphics (hero, project cards, footer links) from projects.yaml, outlining all text to paths so no web fonts are needed."""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

import yaml
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "scripts" / "fonts"
ASSETS = ROOT / "assets"

# Dark matches GitHub's dark surfaces; light deepens the accent stops so small gradient text keeps 4.5:1 on white.
THEMES = {
    "dark": dict(page="#0D1117", surface="#161B22", border="#30363D", text="#E6EDF3",
                 muted="#9198A1", faint="#6E7681", g0="#22D3EE", g1="#8B5CF6"),
    "light": dict(page="#FFFFFF", surface="#F6F8FA", border="#D0D7DE", text="#1F2328",
                  muted="#59636E", faint="#818B98", g0="#0E7490", g1="#6D28D9"),
}
GRADIENT = "gradient"   # pass as a fill to paint a text run with the accent gradient


def num(v: float) -> str:
    s = f"{v:.1f}"
    return s[:-2] if s.endswith(".0") else s


def sig(v: float) -> str:
    return f"{v:.5g}"


class Doc:
    """Collects what one SVG file needs in <defs>: each glyph outline once, plus per-run gradients."""

    def __init__(self, theme: dict):
        self.t = theme
        self.glyphs: dict[str, str] = {}
        self.defs: list[str] = []
        self._n = 0

    def gradient(self, x1: float, x2: float) -> str:
        self._n += 1
        gid = f"g{self._n}"
        self.defs.append(f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="{num(x1)}" y1="0" '
                         f'x2="{num(x2)}" y2="0"><stop offset="0" stop-color="{self.t["g0"]}"/>'
                         f'<stop offset="1" stop-color="{self.t["g1"]}"/></linearGradient>')
        return f"url(#{gid})"

    def render(self, w: int, h: int, title: str, body: str, style: str = "") -> str:
        glyphs = "".join(f'<path id="{k}" d="{d}"/>' for k, d in self.glyphs.items())
        style_el = (f"<style>{style}@media (prefers-reduced-motion: reduce){{*{{animation:none!important}}}}</style>"
                    if style else "")
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
                f'role="img" aria-labelledby="t"><title id="t">{escape(title)}</title>{style_el}'
                f'<defs>{glyphs}{"".join(self.defs)}</defs>{body}</svg>\n')


class Face:
    """One font file, able to measure and outline a string with GPOS kerning and optional tabular figures."""

    def __init__(self, filename: str, key: str):
        self.key = key
        self.font = TTFont(FONTS / filename)
        self.upm = self.font["head"].unitsPerEm
        self.cmap = self.font.getBestCmap()
        self.glyphset = self.font.getGlyphSet()
        self.order = {g: i for i, g in enumerate(self.font.getGlyphOrder())}
        self.hmtx = self.font["hmtx"]
        self._kern = self._compile_kern()
        self._tnum = {}
        for subtables in self._lookups("GSUB", "tnum"):
            for st in subtables:
                if hasattr(st, "mapping"):
                    self._tnum.update(st.mapping)

    def _lookups(self, table: str, tag: str) -> list[list]:
        if table not in self.font:
            return []
        t = self.font[table].table
        extension = 7 if table == "GSUB" else 9
        idx = sorted({i for fr in t.FeatureList.FeatureRecord if fr.FeatureTag == tag
                      for i in fr.Feature.LookupListIndex})
        out = []
        for i in idx:
            lk = t.LookupList.Lookup[i]
            out.append([st.ExtSubTable if lk.LookupType == extension else st for st in lk.SubTable])
        return out

    def _compile_kern(self) -> list[list]:
        lookups = []
        for subtables in self._lookups("GPOS", "kern"):
            compiled = []
            for st in subtables:
                if getattr(st, "Format", None) == 1 and hasattr(st, "PairSet"):
                    pairs = {g: {r.SecondGlyph: getattr(r.Value1, "XAdvance", 0) or 0 for r in ps.PairValueRecord}
                             for g, ps in zip(st.Coverage.glyphs, st.PairSet)}
                    compiled.append((1, pairs))
                elif getattr(st, "Format", None) == 2 and hasattr(st, "Class1Record"):
                    compiled.append((2, (set(st.Coverage.glyphs), st.ClassDef1.classDefs,
                                         st.ClassDef2.classDefs, st.Class1Record)))
            lookups.append(compiled)
        return lookups

    def kern(self, a: str, b: str) -> int:
        total = 0
        for compiled in self._kern:
            for fmt, data in compiled:
                if fmt == 1:
                    if a in data and b in data[a]:
                        total += data[a][b]
                        break
                else:
                    cov, cd1, cd2, rec = data
                    if a in cov:
                        v = rec[cd1.get(a, 0)].Class2Record[cd2.get(b, 0)].Value1
                        total += getattr(v, "XAdvance", 0) or 0
                        break
        return total

    def shape(self, text: str, size: float, tracking: float = 0.0, tnum: bool = False):
        names = []
        for ch in text:
            g = self.cmap.get(ord(ch))
            if g is None:
                raise ValueError(f"{ch!r} is missing from {self.font.reader.file.name}")
            names.append(self._tnum.get(g, g) if tnum else g)
        scale = size / self.upm
        placed, x = [], 0.0
        for i, g in enumerate(names):
            placed.append((g, x))
            adv = self.hmtx[g][0] + (self.kern(g, names[i + 1]) if i + 1 < len(names) else 0)
            x += adv * scale + tracking
        return placed, (x - tracking if names else 0.0)

    def width(self, text: str, size: float, tracking: float = 0.0, tnum: bool = False) -> float:
        return self.shape(text, size, tracking, tnum)[1]

    def _glyph_id(self, doc: Doc, g: str) -> str | None:
        gid = f"{self.key}{self.order[g]}"
        if gid not in doc.glyphs:
            pen = SVGPathPen(self.glyphset, ntos=lambda v: str(round(v)))
            self.glyphset[g].draw(pen)
            d = pen.getCommands()
            if not d:
                return None      # spaces and other blank glyphs
            doc.glyphs[gid] = d
        return gid

    def text(self, doc: Doc, s: str, x: float, y: float, size: float, fill: str,
             anchor: str = "start", tracking: float = 0.0, tnum: bool = False) -> str:
        placed, w = self.shape(s, size, tracking, tnum)
        x -= {"start": 0, "middle": w / 2, "end": w}[anchor]
        if fill == GRADIENT:
            fill = doc.gradient(x, x + w)
        k = sig(size / self.upm)
        uses = []
        for g, gx in placed:
            gid = self._glyph_id(doc, g)
            if gid:
                uses.append(f'<use href="#{gid}" transform="matrix({k} 0 0 -{k} {num(x + gx)} {num(y)})"/>')
        return f'<g fill="{fill}">{"".join(uses)}</g>'

    def wrap(self, s: str, size: float, max_width: float) -> list[str]:
        lines, line = [], ""
        for word in s.split():
            trial = f"{line} {word}".strip()
            if line and self.width(trial, size) > max_width:
                lines.append(line)
                line = word
            else:
                line = trial
        return lines + [line] if line else lines


SANS = Face("Inter-Regular.ttf", "r")
BOLD = Face("Inter-Bold.ttf", "b")
MONO = Face("IBMPlexMono-Medium.ttf", "m")


# ---------- Hero ----------

PULSE_S = 5.8          # one full cascade plus a short rest, kept under 6s
STAGE_S = PULSE_S * 0.22


def pipeline_graph(doc: Doc, x0: float, x1: float, cy: float, stages: list[str]) -> tuple[str, str]:
    """A small left-to-right DAG; a gradient pulse cascades along each stage's edges in turn."""
    t = doc.t
    columns = [[-60, 0, 60], [-32, 32], [-46, 46], [0], [0]]
    xs = [x0 + i * (x1 - x0) / (len(columns) - 1) for i in range(len(columns))]
    edge_grad = doc.gradient(x0, x1)
    edges, pulses = [], []
    for k in range(len(columns) - 1):
        for ya in columns[k]:
            for yb in columns[k + 1]:
                xa, xb = xs[k], xs[k + 1]
                mid = (xa + xb) / 2
                d = (f"M{num(xa)} {num(cy + ya)}C{num(mid)} {num(cy + ya)} {num(mid)} {num(cy + yb)} "
                     f"{num(xb)} {num(cy + yb)}")
                edges.append(f'<path d="{d}"/>')
                pulses.append(f'<path style="animation-delay:{k * STAGE_S:.2f}s" pathLength="100" d="{d}"/>')
    nodes = []
    for k, col in enumerate(columns):
        for y in col:
            cx, cyy = num(xs[k]), num(cy + y)
            if k == len(columns) - 1:
                nodes.append(f'<circle class="ring" cx="{cx}" cy="{cyy}" r="7" fill="none" stroke="{edge_grad}" stroke-width="1.5"/>'
                             f'<circle cx="{cx}" cy="{cyy}" r="7" fill="{edge_grad}"/>')
            else:
                nodes.append(f'<circle cx="{cx}" cy="{cyy}" r="4.5" fill="{t["page"]}" stroke="{t["faint"]}" stroke-width="1.5"/>')
    labels = "".join(MONO.text(doc, s, xs[i], cy + 100, 11, t["faint"], anchor="middle", tracking=0.6)
                     for i, s in enumerate(stages))
    body = (f'<g fill="none" stroke="{t["border"]}" stroke-width="1.25">{"".join(edges)}</g>'
            f'<g class="p" fill="none" stroke="{edge_grad}">{"".join(pulses)}</g>{"".join(nodes)}{labels}')
    ring_delay = (len(columns) - 1) * STAGE_S
    style = (f".p path{{stroke-width:2;stroke-linecap:round;stroke-dasharray:16 200;stroke-dashoffset:-100;"
             f"animation:flow {PULSE_S}s cubic-bezier(.45,0,.55,1) infinite}}"
             f"@keyframes flow{{0%{{stroke-dashoffset:16}}22%{{stroke-dashoffset:-100}}100%{{stroke-dashoffset:-100}}}}"
             f".ring{{opacity:0;transform-box:fill-box;transform-origin:center;"
             f"animation:ring {PULSE_S}s ease-out {ring_delay:.2f}s infinite}}"
             f"@keyframes ring{{0%{{opacity:.8;transform:scale(1)}}14%{{opacity:0;transform:scale(2.4)}}"
             f"100%{{opacity:0;transform:scale(2.4)}}}}")
    return body, style


def hero_title(cfg: dict) -> str:
    return f'{cfg["name"]}, {cfg["eyebrow"].title()}. {cfg["line"]}'


def hero(cfg: dict, t: dict) -> str:
    doc = Doc(t)
    w, h, pad = 1200, 320, 64
    graph_x0, graph_x1 = 790, 1120
    line_size = 18
    assert SANS.width(cfg["line"], line_size) < graph_x0 - 80 - pad, "positioning line runs into the graph"
    graph, style = pipeline_graph(doc, graph_x0, graph_x1, 158, cfg["stages"])
    doc.defs.append(f'<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">'
                    f'<circle cx="1" cy="1" r="1" fill="{t["border"]}"/></pattern>'
                    f'<linearGradient id="fade" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
                    f'<stop offset=".45" stop-color="#fff" stop-opacity=".9"/><stop offset="1" stop-color="#fff" stop-opacity=".9"/>'
                    f'</linearGradient><mask id="m"><rect x="640" y="1" width="559" height="318" fill="url(#fade)"/></mask>')
    body = (f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="16" fill="{t["page"]}" stroke="{t["border"]}"/>'
            f'<rect x="640" y="1" width="559" height="318" fill="url(#dots)" mask="url(#m)" opacity=".7"/>'
            + MONO.text(doc, cfg["eyebrow"], pad, 112, 15, GRADIENT, tracking=2.2)
            + BOLD.text(doc, cfg["name"], pad, 180, 64, t["text"], tracking=-1.6)
            + SANS.text(doc, cfg["line"], pad, 226, line_size, t["muted"])
            + MONO.text(doc, cfg["meta"], pad, 268, 13, t["faint"], tracking=0.4)
            + graph)
    return doc.render(w, h, hero_title(cfg), body, style)


def hero_compact(cfg: dict, t: dict) -> str:
    """Narrow-screen hero: same words, stacked, no graph, so text stays legible on a phone."""
    doc = Doc(t)
    w, h, pad = 640, 360, 40
    lines = SANS.wrap(cfg["line"], 26, w - 2 * pad)
    y_rule = 204 + len(lines) * 36 - 6
    body = (f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="16" fill="{t["page"]}" stroke="{t["border"]}"/>'
            + MONO.text(doc, cfg["eyebrow"], pad, 84, 17, GRADIENT, tracking=2)
            + BOLD.text(doc, cfg["name"], pad, 152, 58, t["text"], tracking=-1.4)
            + "".join(SANS.text(doc, s, pad, 204 + i * 36, 26, t["muted"]) for i, s in enumerate(lines))
            + f'<rect x="{pad}" y="{y_rule}" width="56" height="3" rx="1.5" fill="{doc.gradient(pad, pad + 56)}"/>'
            + MONO.text(doc, cfg["meta"], pad, y_rule + 40, 16, t["faint"], tracking=0.4))
    return doc.render(w, h, hero_title(cfg), body)


# ---------- Cards ----------

CARD_W, CARD_H, CARD_PAD = 420, 232, 24


def chip_row(doc: Doc, chips: list[str], x: float, y: float) -> str:
    out, size, h = [], 10.5, 22
    start = x
    for c in chips:
        cw = MONO.width(c, size, tracking=0.2) + 20
        out.append(f'<rect x="{num(x + .5)}" y="{num(y + .5)}" width="{num(cw - 1)}" height="{h - 1}" rx="{h / 2}" '
                   f'fill="none" stroke="{doc.gradient(x, x + cw)}" stroke-opacity=".75"/>')
        out.append(MONO.text(doc, c, x + 10, y + 15, size, doc.t["text"], tracking=0.2))
        x += cw + 8
    assert x - 8 - start <= CARD_W - 2 * CARD_PAD, f"chips overflow: {chips}"
    return "".join(out)


def arrow(x: float, y: float, s: float, color: str) -> str:
    """A north-east arrow drawn as strokes, top-left corner at (x, y)."""
    return (f'<path d="M{num(x)} {num(y + s)}L{num(x + s)} {num(y)}M{num(x + s * .35)} {num(y)}H{num(x + s)}'
            f'V{num(y + s * .65)}" fill="none" stroke="{color}" stroke-width="1.6" stroke-linecap="round" '
            f'stroke-linejoin="round"/>')


def card_alt(c: dict) -> str:
    return (f'{c["title"]}: {c["problem"]} {c["metric"]} {" ".join(c["metric_label"])} '
            f'Built with {", ".join(c["chips"])}.')


def card(c: dict, t: dict) -> str:
    doc = Doc(t)
    w, h, pad = CARD_W, CARD_H, CARD_PAD
    parts = [f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="12" fill="{t["surface"]}" stroke="{t["border"]}"/>',
             MONO.text(doc, c["kicker"], pad, 38, 10.5, t["faint"], tracking=1.2)]
    if c.get("status"):
        sw = MONO.width(c["status"], 10.5, tracking=1.2)
        assert MONO.width(c["kicker"], 10.5, tracking=1.2) + sw + 40 < w - 2 * pad, f'{c["slug"]}: kicker collides'
        parts.append(MONO.text(doc, c["status"], w - pad, 38, 10.5, t["muted"], anchor="end", tracking=1.2))
        dot_x = w - pad - sw - 9
        parts.append(f'<circle cx="{num(dot_x)}" cy="34.5" r="3.5" fill="{doc.gradient(dot_x - 3.5, dot_x + 3.5)}"/>')
    parts.append(BOLD.text(doc, c["title"], pad, 70, 21, t["text"], tracking=-0.3))
    if c.get("repo"):
        parts.append(arrow(pad + BOLD.width(c["title"], 21, tracking=-0.3) + 9, 56, 10, t["muted"]))
    lines = SANS.wrap(c["problem"], 13, w - 2 * pad)
    assert len(lines) <= 2, f'{c["slug"]}: problem line wraps to {len(lines)} lines'
    parts += [SANS.text(doc, s, pad, 96 + i * 18, 13, t["muted"]) for i, s in enumerate(lines)]
    mw = BOLD.width(c["metric"], 36, tracking=-0.6, tnum=True)
    parts.append(BOLD.text(doc, c["metric"], pad, 166, 36, GRADIENT, tracking=-0.6, tnum=True))
    lx = pad + mw + 14
    for i, s in enumerate(c["metric_label"]):
        assert MONO.width(s, 10.5) < w - pad - lx, f'{c["slug"]}: metric label "{s}" too wide'
        parts.append(MONO.text(doc, s, lx, 150 + i * 15, 10.5, t["muted"]))
    parts.append(chip_row(doc, c["chips"], pad, 186))
    return doc.render(w, h, card_alt(c), "".join(parts))


# ---------- Toolkit and stack chips ----------

ICONS_DIR = ROOT / "scripts" / "icons"
SIMPLE_ICONS = "https://cdn.jsdelivr.net/npm/simple-icons@16.30.0/icons/{}.svg"
SIMPLE_ICONS_DATA = "https://cdn.jsdelivr.net/npm/simple-icons@16.30.0/data/simple-icons.json"


def _fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read()


def icon_path(slug: str) -> str:
    """The 24x24 path data for a Simple Icons slug, downloaded once and vendored in scripts/icons."""
    f = ICONS_DIR / f"{slug}.svg"
    if not f.exists():
        ICONS_DIR.mkdir(parents=True, exist_ok=True)
        f.write_bytes(_fetch(SIMPLE_ICONS.format(slug)))
    return re.search(r'<path d="([^"]+)"', f.read_text(encoding="utf-8")).group(1)


def brand_hex(slug: str) -> str:
    f = ICONS_DIR / "_colours.json"
    if not f.exists():
        data = json.loads(_fetch(SIMPLE_ICONS_DATA))
        f.write_text(json.dumps({i["slug"]: i["hex"] for i in data}, indent=0, sort_keys=True), encoding="utf-8")
    return "#" + json.loads(f.read_text(encoding="utf-8"))[slug]


def contrast(a: str, b: str) -> float:
    def lum(h: str) -> float:
        rgb = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        rgb = [c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4 for c in rgb]
        return .2126 * rgb[0] + .7152 * rgb[1] + .0722 * rgb[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + .05) / (lo + .05)


def tool_mark(doc: Doc, spec: dict, x: float, y: float, s: float, ground: str, style: str) -> str:
    """The 's'-sized mark at (x, y): a brand icon, a lettered badge, or an accent dot for a practice."""
    t = doc.t
    if "icon" in spec:
        fill = t["text"]
        if style == "brand":
            hexc = brand_hex(spec["icon"])
            fill = hexc if contrast(hexc, ground) >= 3 else t["text"]
        return f'<path transform="translate({num(x)} {num(y)}) scale({sig(s / 24)})" fill="{fill}" d="{icon_path(spec["icon"])}"/>'
    if "mono" in spec:
        letters = spec["mono"]
        size = s * (.42 if len(letters) <= 2 else .34)
        return (f'<rect x="{num(x + .5)}" y="{num(y + .5)}" width="{num(s - 1)}" height="{num(s - 1)}" rx="{num(s * .25)}" '
                f'fill="none" stroke="{t["muted"]}"/>'
                + MONO.text(doc, letters, x + s / 2, y + s / 2 + size * .36, size, t["text"], anchor="middle"))
    r = s * .2
    return f'<circle cx="{num(x + s / 2)}" cy="{num(y + s / 2)}" r="{num(r)}" fill="{doc.gradient(x + s / 2 - r, x + s / 2 + r)}"/>'


def flow_tiles(doc: Doc, names: list[str], tools: dict, x0: float, x1: float, y0: float, *, h: float,
               font: float, icon: float, ground: str, fill: str, style: str) -> tuple[str, float]:
    """Lays tiles left to right, wrapping at x1; returns the markup and the bottom edge."""
    t, out = doc.t, []
    gap, pad_l, pad_r, inner = 8, (h - icon) / 2 + 1, 12, 8
    x, y = x0, y0
    for name in names:
        spec = tools[name]
        tw = pad_l + icon + inner + SANS.width(name, font) + pad_r
        if x > x0 and x + tw > x1:
            x, y = x0, y + h + gap
        assert tw <= x1 - x0, f"tile {name!r} wider than its row"
        out.append(f'<rect x="{num(x + .5)}" y="{num(y + .5)}" width="{num(tw - 1)}" height="{num(h - 1)}" rx="8" '
                   f'fill="{fill}" stroke="{t["border"]}"/>')
        out.append(tool_mark(doc, spec, x + pad_l, y + (h - icon) / 2, icon, ground, style))
        out.append(SANS.text(doc, name, x + pad_l + icon + inner, y + h / 2 + font * .36, font, t["text"]))
        x += tw + gap
    return "".join(out), y + h


def toolkit_group(g: dict, tools: dict, style: str, t: dict, compact: bool = False) -> str:
    doc = Doc(t)
    if compact:
        w, pad = 480, 18
        tiles, bottom = flow_tiles(doc, g["items"], tools, pad, w - pad, pad + 30, h=36, font=15, icon=18,
                                   ground=t["page"], fill=t["page"], style=style)
        label = (f'<rect x="{pad}" y="{pad + 3}" width="3" height="16" rx="1.5" fill="{doc.gradient(pad, pad + 3)}"/>'
                 + BOLD.text(doc, g["group"], pad + 11, pad + 16, 16, t["text"]))
    else:
        w, pad, label_w = 880, 18, 196
        tiles, bottom = flow_tiles(doc, g["items"], tools, pad + label_w, w - pad, pad, h=32, font=13, icon=16,
                                   ground=t["page"], fill=t["page"], style=style)
        label = (f'<rect x="{pad + 4}" y="{pad + 8}" width="3" height="16" rx="1.5" fill="{doc.gradient(pad + 4, pad + 7)}"/>'
                 + BOLD.text(doc, g["group"], pad + 16, pad + 21, 14, t["text"]))
    h = round(bottom + pad)
    body = (f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="12" fill="{t["surface"]}" stroke="{t["border"]}"/>'
            + label + tiles)
    return doc.render(w, h, f'{g["group"]}: {", ".join(g["items"])}', body)


def work_row(p: dict, tools: dict, style: str, t: dict, compact: bool = False) -> str:
    """One 'More work' project: linked title, the finding in plain words, and its stack as icon chips."""
    doc = Doc(t)
    if compact:
        w, pad, font, lh = 480, 20, 15, 22
        title_y = pad + 18
        lines = SANS.wrap(p["text"], font, w - 2 * pad)
        text_bottom = title_y + 12 + len(lines) * lh
        tiles, bottom = flow_tiles(doc, p["items"], tools, pad, w - pad, text_bottom + 6, h=30, font=13, icon=15,
                                   ground=t["page"], fill=t["page"], style=style)
        title_size, text_x, text_y0 = 17, pad, title_y + 12 + font
    else:
        w, pad, font, lh, split = 880, 20, 13, 19, 560
        title_y = pad + 16
        lines = SANS.wrap(p["text"], font, split - pad - 24)
        text_bottom = title_y + 8 + len(lines) * lh
        tiles, bottom = flow_tiles(doc, p["items"], tools, split, w - pad, pad, h=28, font=12, icon=14,
                                   ground=t["page"], fill=t["page"], style=style)
        title_size, text_x, text_y0 = 15, pad, title_y + 10 + font
    assert len(lines) <= 3 or compact, f'{p["slug"]}: description wraps to {len(lines)} lines'
    h = round(max(text_bottom, bottom) + pad)
    title_w = BOLD.width(p["title"], title_size, tracking=-0.2)
    body = (f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="12" fill="{t["surface"]}" stroke="{t["border"]}"/>'
            + BOLD.text(doc, p["title"], pad, title_y, title_size, t["text"], tracking=-0.2)
            + arrow(pad + title_w + 7, title_y - title_size * .62, title_size * .5, t["muted"])
            + "".join(SANS.text(doc, s, text_x, text_y0 + i * lh, font, t["muted"]) for i, s in enumerate(lines))
            + tiles)
    return doc.render(w, h, f'{p["title"]}: {p["text"]} Stack: {", ".join(p["items"])}.', body)


# ---------- Footer links ----------

ICONS = {
    # 16x16 stroke icons, drawn at the origin
    "mail": '<rect x="1" y="3" width="14" height="10" rx="2"/><path d="M1.5 4.5 8 9l6.5-4.5"/>',
    "linkedin": '<rect x="1" y="1" width="14" height="14" rx="3"/><path d="M5 7v4.5M5 4.6v.1M8 11.5V7m0 2.2c0-1.4.9-2.2 2-2.2s2 .8 2 2.2v2.3"/>',
    "folder": '<path d="M1.5 4.5a1.5 1.5 0 0 1 1.5-1.5h3l1.5 1.8H13a1.5 1.5 0 0 1 1.5 1.5v5.7A1.5 1.5 0 0 1 13 13.5H3A1.5 1.5 0 0 1 1.5 12z"/>',
}


def footer_link(link: dict, t: dict) -> str:
    doc = Doc(t)
    size, h = 13, 36
    tw = SANS.width(link["label"], size)
    w = round(14 + 16 + 8 + tw + 16)
    body = (f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="{h / 2}" fill="none" stroke="{t["border"]}"/>'
            f'<g transform="translate(14 10)" fill="none" stroke="{t["muted"]}" stroke-width="1.4" '
            f'stroke-linecap="round" stroke-linejoin="round">{ICONS[link["icon"]]}</g>'
            + SANS.text(doc, link["label"], 38, 22.5, size, t["text"]))
    return doc.render(w, h, link["label"], body)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="comma-separated: hero, footer, toolkit, work and/or card slugs")
    ap.add_argument("--icon-style", choices=["mono", "brand"], help="override icon_style in projects.yaml")
    args = ap.parse_args()
    cfg = yaml.safe_load((ROOT / "scripts" / "projects.yaml").read_text(encoding="utf-8"))
    only = set(args.only.split(",")) if args.only else None
    tools, style = cfg["tools"], args.icon_style or cfg.get("icon_style", "mono")
    for name in [n for g in cfg["toolkit"] + cfg["more_work"] for n in g["items"]]:
        assert name in tools, f"{name!r} is used but missing from tools:"
    jobs = []
    if not only or "hero" in only:
        jobs += [(f"hero-{{m}}.svg", hero, cfg["hero"]), (f"hero-compact-{{m}}.svg", hero_compact, cfg["hero"])]
    jobs += [(f'cards/{c["slug"]}-{{m}}.svg', card, c) for c in cfg["cards"] if not only or c["slug"] in only]
    if not only or "footer" in only:
        jobs += [(f'footer/{f["slug"]}-{{m}}.svg', footer_link, f) for f in cfg["footer"]]
    if not only or "toolkit" in only:
        for g in cfg["toolkit"]:
            jobs.append((f'toolkit/{g["slug"]}-{{m}}.svg', lambda d, t: toolkit_group(d, tools, style, t), g))
            jobs.append((f'toolkit/{g["slug"]}-compact-{{m}}.svg', lambda d, t: toolkit_group(d, tools, style, t, True), g))
    if not only or "work" in only:
        for p in cfg["more_work"]:
            jobs.append((f'work/{p["slug"]}-{{m}}.svg', lambda d, t: work_row(d, tools, style, t), p))
            jobs.append((f'work/{p["slug"]}-compact-{{m}}.svg', lambda d, t: work_row(d, tools, style, t, True), p))
    for pattern, fn, data in jobs:
        for mode, t in THEMES.items():
            p = ASSETS / pattern.format(m=mode)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(fn(data, t), encoding="utf-8")
            kb = p.stat().st_size / 1024
            assert kb < 80, f"{p.name} is {kb:.0f} KB"
            print(f"{p.relative_to(ROOT).as_posix():38} {kb:5.1f} KB")


if __name__ == "__main__":
    main()
