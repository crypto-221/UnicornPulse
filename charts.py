"""Server-side SVG charts (no JavaScript needed). Hover tooltips use native <title>."""
import math

from markupsafe import Markup, escape


def _nice_ticks(maxv, n=4):
    if maxv <= 0:
        return [0, 1]
    raw = maxv / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 5, 10) if m * mag >= raw)
    return [step * i for i in range(n + 1)]


def _b(e):
    v = 10 ** e
    return f"${round(v * 1000, 6):g}M" if v < 1 else f"${v:g}B"


def timeline_svg(years, counts) -> Markup:
    W, H, L, R, T, B = 640, 260, 40, 14, 14, 28
    ticks = _nice_ticks(max(counts))
    ymax = ticks[-1]
    y0, y1 = years[0], years[-1]
    span = max(y1 - y0, 1)
    px = lambda y: L + (y - y0) / span * (W - L - R)
    py = lambda v: T + (1 - v / ymax) * (H - T - B)

    p = [f'<svg class="chart-svg" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="New unicorns per year">']
    for t in ticks:
        p.append(f'<line class="svg-grid" x1="{L}" x2="{W - R}" y1="{py(t):.1f}" y2="{py(t):.1f}"/>')
        p.append(f'<text class="svg-text" x="{L - 8}" y="{py(t) + 4:.1f}" text-anchor="end">{t:g}</text>')
    for y in years:
        if (y - y0) % 3 == 0:
            p.append(f'<text class="svg-text" x="{px(y):.1f}" y="{H - 8}" text-anchor="middle">{y}</text>')
    pts = " ".join(f"{px(y):.1f},{py(c):.1f}" for y, c in zip(years, counts))
    base = py(0)
    p.append(f'<polygon class="svg-area" points="{px(y0):.1f},{base:.1f} {pts} {px(y1):.1f},{base:.1f}"/>')
    p.append(f'<polyline class="svg-line" points="{pts}"/>')
    for y, c in zip(years, counts):
        p.append(f'<circle class="svg-pt" cx="{px(y):.1f}" cy="{py(c):.1f}" r="5">'
                 f'<title>{y}: {c} new unicorn{"s" if c != 1 else ""}</title></circle>')
    p.append("</svg>")
    return Markup("".join(p))


def scatter_svg(points) -> Markup:
    pts = [q for q in points if q["Funding_B"] > 0 and q["Valuation_B"] > 0]
    W, H, L, R, T, B = 640, 340, 56, 14, 12, 40
    xs = [math.log10(q["Funding_B"]) for q in pts]
    ys = [math.log10(q["Valuation_B"]) for q in pts]
    x_lo, x_hi = math.floor(min(xs)), math.ceil(max(xs))
    y_lo, y_hi = math.floor(min(ys)), math.ceil(max(ys))
    x_hi = x_hi if x_hi > x_lo else x_lo + 1
    y_hi = y_hi if y_hi > y_lo else y_lo + 1
    sx = lambda e: L + (e - x_lo) / (x_hi - x_lo) * (W - L - R)
    sy = lambda e: T + (1 - (e - y_lo) / (y_hi - y_lo)) * (H - T - B)

    p = [f'<svg class="chart-svg" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="Valuation versus funding raised">']
    for e in range(x_lo, x_hi + 1):
        p.append(f'<line class="svg-grid" x1="{sx(e):.1f}" x2="{sx(e):.1f}" y1="{T}" y2="{H - B}"/>')
        p.append(f'<text class="svg-text" x="{sx(e):.1f}" y="{H - B + 16}" text-anchor="middle">{_b(e)}</text>')
    for e in range(y_lo, y_hi + 1):
        p.append(f'<line class="svg-grid" x1="{L}" x2="{W - R}" y1="{sy(e):.1f}" y2="{sy(e):.1f}"/>')
        p.append(f'<text class="svg-text" x="{L - 8}" y="{sy(e) + 4:.1f}" text-anchor="end">{_b(e)}</text>')
    lo, hi = max(x_lo, y_lo), min(x_hi, y_hi)
    if lo < hi:
        p.append(f'<line class="svg-diag" x1="{sx(lo):.1f}" y1="{sy(lo):.1f}" x2="{sx(hi):.1f}" y2="{sy(hi):.1f}"/>')
    for q, x, y in zip(pts, xs, ys):
        p.append(f'<circle class="svg-dot" cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="3.2"><title>'
                 f'{escape(q["Company"])}: ${q["Funding_B"]:g}B raised → ${q["Valuation_B"]:g}B valuation</title></circle>')
    p.append(f'<text class="svg-text" x="{(L + W - R) / 2:.0f}" y="{H - 4}" text-anchor="middle">Funding raised (log scale)</text>')
    p.append(f'<text class="svg-text" transform="translate(12 {(T + H - B) / 2:.0f}) rotate(-90)" text-anchor="middle">Valuation (log scale)</text>')
    p.append("</svg>")
    return Markup("".join(p))
