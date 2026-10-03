#!/usr/bin/env python3
"""Re-skin the Platane/snk contribution snake as a pixel-art Michael Scott.

The snk SVG draws the snake as four <rect class="s sN"> elements whose
positions are CSS keyframe animations, and every cell / progress bar is
animated on the same timeline.  This script keeps that timeline but:

  * swaps the snake for a pixel-art Michael Scott (head) and a paper trail
  * slows the whole animation down (--slow, default 1.5x longer)
  * freezes everything for --pause milliseconds (default 2000) each time
    Michael pops a speech bubble, then resumes

Usage: snakeify.py <svg> [<svg> ...] [--slow 1.5] [--pause 2000] [--report out.json]
"""
import argparse
import json
import re

PX = 2  # one sprite pixel in SVG units (a grid cell is 12x12 on a 16px pitch)

MICHAEL_ROWS = [
    "...hhhhhh...",
    "..hhhhhhhh..",
    ".hhhhhhhhhh.",
    ".hhssssssshh",
    ".hssssssssh.",
    ".hsesssssesh",
    "..ssssssss..",
    "..ssssssss..",
    "..sswwwwss..",
    "...ssssss...",
    "..ddccccdd..",
    ".dddcttcddd.",
    "ddddcttcdddd",
    "dddddttddddd",
]
MICHAEL_PALETTE = {
    "h": "#2b1a0e",  # hair
    "s": "#f3c9a4",  # skin
    "e": "#141414",  # eyes
    "w": "#ffffff",  # that smile
    "d": "#1c2740",  # suit
    "c": "#f4f4f4",  # shirt
    "t": "#b3202a",  # tie
}
QUOTES = ["I DECLARE BANKRUPTCY!", "no, God, please, no!", "I understand nothing.", "okay, it’s happening!"]
OUTLINE = "#0b0b0b"


# ----------------------------------------------------------------- sprites
def pixel_rects(rows, palette, x0, y0, px=PX):
    outline, colors = [], []
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch == "." or ch not in palette:
                continue
            x, y = x0 + i * px, y0 + j * px
            outline.append(
                '<rect x="%s" y="%s" width="%s" height="%s" fill="%s"/>' % (x - 1, y - 1, px + 2, px + 2, OUTLINE)
            )
            colors.append('<rect x="%s" y="%s" width="%s" height="%s" fill="%s"/>' % (x, y, px, px, palette[ch]))
    return outline, colors


def paper_sheet():
    return (
        '<rect x="3.5" y="2.5" width="9" height="11" fill="#ffffff" stroke="#444" stroke-width="1"/>'
        '<rect x="5" y="5" width="6" height="1" fill="#9a9a9a"/>'
        '<rect x="5" y="7.5" width="6" height="1" fill="#9a9a9a"/>'
        '<rect x="5" y="10" width="4" height="1" fill="#9a9a9a"/>'
    )


def bubble(idx, text, y=-27):
    width = max(60, int(len(text) * 5.1) + 14)
    x, h = 16, 14
    return (
        '<g class="b b%d">' % idx
        + '<polygon points="%s,%s %s,%s %s,%s" fill="#ffffff" stroke="#111" stroke-width="1"/>'
        % (x + 4, y + h - 1, x - 2, y + h + 7, x + 13, y + h - 1)
        + '<rect x="%s" y="%s" width="%s" height="%s" rx="4" ry="4" fill="#ffffff" stroke="#111" stroke-width="1"/>'
        % (x, y, width, h)
        + '<text x="%s" y="%s" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" '
        'font-size="8.5" font-weight="700" fill="#111" textLength="%s" lengthAdjust="spacingAndGlyphs">%s</text>'
        % (x + width / 2, y + 10, width - 10, text)
        + "</g>"
    )


# ------------------------------------------------------------ keyframes
def pct(p):
    return ("%.3f" % p).rstrip("0").rstrip(".") + "%"


def parse_transform(props):
    m = re.search(r"transform:(\w+)\(([^)]*)\)", props)
    if not m:
        return None
    nums, units = [], []
    for part in m.group(2).split(","):
        mm = re.match(r"\s*(-?[\d.]+)([a-z%]*)\s*$", part)
        nums.append(float(mm.group(1)))
        units.append(mm.group(2))
    return m.group(1), nums, units


def fmt_transform(fn, nums, units):
    return "transform:%s(%s)" % (fn, ",".join(("%g" % round(n, 3)) + u for n, u in zip(nums, units)))


def value_at(entries, p):
    """Linear interpolation of a transform keyframe list at percent p."""
    if p <= entries[0][0]:
        return entries[0][1]
    for (p0, v0), (p1, v1) in zip(entries, entries[1:]):
        if p0 <= p <= p1:
            if p1 == p0:
                return v1
            f = (p - p0) / (p1 - p0)
            return [a + (b - a) * f for a, b in zip(v0, v1)]
    return entries[-1][1]


def keyframe_blocks(css):
    """Yield (start, end, name, body) for every @keyframes block (brace aware)."""
    i = 0
    while True:
        m = re.compile(r"@keyframes\s+([\w-]+)\s*\{").search(css, i)
        if not m:
            return
        depth, j = 1, m.end()
        while j < len(css) and depth:
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
            j += 1
        yield m.start(), j, m.group(1), css[m.end() : j - 1]
        i = j


def head_path(css):
    for _, _, name, body in keyframe_blocks(css):
        if name == "s0":
            pts = []
            for sel, props in re.findall(r"([\d.%,]+)\{([^}]*)\}", body):
                t = parse_transform(props)
                for p in sel.split(","):
                    pts.append((float(p.rstrip("%")), t[1][0], t[1][1]))
            pts.sort()
            return pts
    return []


def head_at(pts, t):
    if not pts:
        return (0.0, -16.0)
    if t <= pts[0][0]:
        return pts[0][1], pts[0][2]
    for (p0, x0, y0), (p1, x1, y1) in zip(pts, pts[1:]):
        if p0 <= t <= p1:
            if p1 == p0:
                return x1, y1
            f = (t - p0) / (p1 - p0)
            return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
    return pts[-1][1], pts[-1][2]


def talk_points(pts, n, x_min=112.0, x_max=700.0, min_gap=8.0):
    """Pick n percents, spread over the loop, where Michael is deep inside the grid."""
    step = 0.05
    inside = []
    t = 0.0
    while t <= 100.0:
        x, y = head_at(pts, t)
        inside.append(x_min <= x <= x_max and y >= 0)
        t += step
    runs, i = [], 0
    while i < len(inside):
        if inside[i]:
            j = i
            while j < len(inside) and inside[j]:
                j += 1
            runs.append((i * step, (j - 1) * step))
            i = j
        else:
            i += 1
    runs = [r for r in runs if r[1] - r[0] >= 1.0]
    points = []
    for k in range(n):
        target = 100.0 * (k + 1) / (n + 1)
        if not runs:
            break
        run = min(runs, key=lambda r: 0 if r[0] <= target <= r[1] else min(abs(r[0] - target), abs(r[1] - target)))
        p = min(max(target, run[0] + 0.3), run[1] - 0.3)
        if any(abs(p - q) < min_gap for q in points):
            continue
        points.append(round(p, 2))
    return sorted(points)


def timewarp(css, duration, slow, pauses, pause_ms):
    """Slow the timeline by `slow` and insert a hold of pause_ms at each pause percent.

    Returns (new_css, new_duration_ms, [(start_pct, end_pct), ...]) with the
    pause windows expressed in the new timeline.
    """
    d_slow = duration * slow
    d_new = d_slow + len(pauses) * pause_ms

    def before(p):  # new percent for an original percent, counting pauses strictly before it
        k = sum(1 for q in pauses if q < p)
        return (p / 100.0 * d_slow + k * pause_ms) / d_new * 100.0

    def after(p):  # new percent once the pause AT p (if any) has elapsed
        k = sum(1 for q in pauses if q <= p)
        return (p / 100.0 * d_slow + k * pause_ms) / d_new * 100.0

    windows = [(before(p), after(p)) for p in pauses]
    out, last = [], 0
    for start, end, name, body in keyframe_blocks(css):
        out.append(css[last:start])
        raw = re.findall(r"([\d.%,]+)\{([^}]*)\}", body)
        entries = []
        for sel, props in raw:
            for p in sel.split(","):
                entries.append((float(p.rstrip("%")), props))
        entries.sort(key=lambda e: e[0])
        is_transform = bool(entries) and parse_transform(entries[0][1]) is not None
        new_entries = []
        if is_transform:
            fn, _, units = parse_transform(entries[0][1])
            numeric = [(p, parse_transform(props)[1]) for p, props in entries]
            for p, props in entries:
                new_entries.append((before(p), props))
            for p, (ws, we) in zip(pauses, windows):
                v = value_at(numeric, p)
                held = fmt_transform(fn, v, units)
                new_entries.append((ws, held))
                new_entries.append((we, held))
        else:
            for p, props in entries:
                new_entries.append((before(p), props))
        new_entries.sort(key=lambda e: e[0])
        out.append("@keyframes %s{%s}" % (name, "".join("%s{%s}" % (pct(p), props) for p, props in new_entries)))
        last = end
    out.append(css[last:])
    new_css = "".join(out).replace("%dms" % duration, "%dms" % int(round(d_new)))
    return new_css, int(round(d_new)), windows


# --------------------------------------------------------------- skin
def skin(svg, slow=1.5, pause_ms=2000):
    css_match = re.search(r"<style>(.*?)</style>", svg, re.S)
    if not css_match:
        raise SystemExit("no <style> block found; is this a Platane/snk SVG?")
    css = css_match.group(1)
    dur = re.search(r"\.s\{[^}]*animation:none linear (\d+)ms infinite", css)
    duration = int(dur.group(1)) if dur else 60700
    if not re.search(r'<rect class="s s0"', svg):
        raise SystemExit("no snake head rect found; is this a Platane/snk SVG?")

    pauses = talk_points(head_path(css), len(QUOTES))
    css, new_duration, windows = timewarp(css, duration, slow, pauses, pause_ms)

    extra = [".sp{shape-rendering:crispEdges}", ".b{opacity:0;animation:none linear %dms infinite}" % new_duration]
    bubbles = []
    report = {"original_ms": duration, "duration_ms": new_duration, "slow": slow, "pause_ms": pause_ms, "talks": []}
    for i, (ws, we) in enumerate(windows):
        bubbles.append(bubble(i, QUOTES[i]))
        extra.append(".b.b%d{animation-name:b%d}" % (i, i))
        extra.append(
            "@keyframes b%d{0%%,%s{opacity:0}%s,%s{opacity:1}%s,100%%{opacity:0}}"
            % (i, pct(max(ws - 0.01, 0)), pct(ws), pct(we), pct(min(we + 0.01, 100)))
        )
        report["talks"].append({"start_pct": round(ws, 2), "end_pct": round(we, 2), "text": QUOTES[i]})

    outline, colors = pixel_rects(MICHAEL_ROWS, MICHAEL_PALETTE, x0=8 - 12, y0=8 - 15)
    head = '<g class="s s0"><g class="sp">' + "".join(outline) + "".join(colors) + "</g>" + "".join(bubbles) + "</g>"
    svg = re.sub(r'<rect class="s s0"[^>]*/>', lambda m: head, svg, count=1)
    for n in (1, 2, 3):
        body = '<g class="s s%d">%s</g>' % (n, paper_sheet())
        svg = re.sub(r'<rect class="s s%d"[^>]*/>' % n, lambda m, b=body: b, svg, count=1)
    svg = svg.replace(css_match.group(0), "<style>" + css + "".join(extra) + "</style>", 1)
    return svg, report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--slow", type=float, default=1.5, help="stretch the animation by this factor (1 = original speed)")
    ap.add_argument("--pause", type=int, default=2000, help="milliseconds Michael stands still while a bubble shows")
    ap.add_argument("--report", help="write a JSON report (durations, talk windows)")
    args = ap.parse_args()
    reports = {}
    for path in args.files:
        with open(path, encoding="utf-8") as fh:
            svg = fh.read()
        if '<rect class="s s0"' not in svg:
            print("%s: already re-skinned, skipping" % path)
            continue
        out, rep = skin(svg, args.slow, args.pause)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(out)
        reports[path] = rep
        print("%s: Michael applied (%dms -> %dms loop, %d talk pauses of %dms)"
              % (path, rep["original_ms"], rep["duration_ms"], len(rep["talks"]), args.pause))
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump(reports, fh, indent=1)


if __name__ == "__main__":
    main()
