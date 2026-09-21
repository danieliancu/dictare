"""Small UI helpers available in every template (registered as a builtin)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from django import template
from django.conf import settings
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

ICON_DIR = Path(settings.BASE_DIR) / "templates" / "icons"


@lru_cache(maxsize=128)
def _load_icon(name: str) -> str:
    path = ICON_DIR / f"{name}.svg"
    if not path.is_file() or path.parent != ICON_DIR:
        return ""
    return path.read_text(encoding="utf-8")


@register.simple_tag
def icon(name: str, css_class: str = "icon", label: str = "") -> str:
    """Inline SVG icon. Decorative unless a `label` is given."""
    svg = _load_icon(name)
    if not svg:
        return ""
    a11y = f'role="img" aria-label="{label}"' if label else 'aria-hidden="true" focusable="false"'
    svg = svg.replace("<svg ", f'<svg class="{css_class}" {a11y} ', 1)
    return mark_safe(svg)  # noqa: S308 - trusted files from the repository


@register.simple_tag
def outcome_dots(misses, exposures, cap: int = 12) -> list[bool]:
    """One flag per exposure (True = missed), capped; misses first so the red reads at a glance."""
    exposures, misses = int(exposures or 0), int(misses or 0)
    shown = min(exposures, cap)
    missed = min(misses, shown)
    return [True] * missed + [False] * (shown - missed)


@register.filter
def percent(value, total) -> int:
    try:
        return round(100 * float(value) / float(total)) if float(total) else 0
    except (TypeError, ValueError):
        return 0


@register.filter
def clamp100(value) -> int:
    try:
        return max(0, min(100, round(float(value))))
    except (TypeError, ValueError):
        return 0


@register.simple_tag
def donut(value: int, size: int = 88, stroke: int = 9, label: str = "") -> str:
    """Accessible SVG progress ring."""
    value = max(0, min(100, int(value or 0)))
    r = (size - stroke) / 2
    c = 2 * 3.14159265 * r
    offset = c * (1 - value / 100)
    return format_html(
        '<svg class="donut" width="{s}" height="{s}" viewBox="0 0 {s} {s}" role="img" '
        'aria-label="{label}{v}%">'
        '<circle class="donut__track" cx="{h}" cy="{h}" r="{r}" stroke-width="{w}" fill="none"/>'
        '<circle class="donut__value" style="--donut-c: {c}" cx="{h}" cy="{h}" r="{r}" '
        'stroke-width="{w}" fill="none" '
        'stroke-dasharray="{c}" stroke-dashoffset="{o}" transform="rotate(-90 {h} {h})"/>'
        "</svg>",
        s=size,
        h=size / 2,
        r=r,
        w=stroke,
        c=f"{c:.2f}",
        o=f"{offset:.2f}",
        v=value,
        label=label,
    )


@register.simple_tag(takes_context=True)
def absolute_url(context, path: str = "") -> str:
    base = context.get("SITE_URL") or settings.SITE_URL
    return f"{base}{path}"


@register.filter
def split_lines(value: str) -> list[str]:
    return [line.strip() for line in (value or "").splitlines() if line.strip()]


@register.simple_tag
def waveform_bars(seed: str = "", count: int = 36) -> str:
    """Deterministic decorative waveform (used before real peaks are decoded)."""
    import hashlib
    import math

    digest = hashlib.sha256((seed or "dictare").encode()).digest()
    bars = []
    for i in range(count):
        b = digest[i % len(digest)]
        env = 0.45 + 0.55 * math.sin(math.pi * i / max(count - 1, 1))
        h = max(14, min(100, int((0.3 + (b / 255) * 0.7) * 100 * env)))
        bars.append(f'<span style="--h:{h}%"></span>')
    return mark_safe("".join(bars))


@register.filter
def mmss(milliseconds) -> str:
    """Format a duration in milliseconds as m:ss."""
    try:
        total = max(0, round(int(milliseconds) / 1000))
    except (TypeError, ValueError):
        return "0:00"
    return f"{total // 60}:{total % 60:02d}"


@register.filter
def pick(value, options: str) -> str:
    """Stable choice from a comma-separated list, e.g. a colour per id: {{ id|pick:"a,b,c" }}."""
    items = [o.strip() for o in options.split(",") if o.strip()]
    try:
        return items[int(value) % len(items)] if items else ""
    except (TypeError, ValueError):
        return items[0] if items else ""


@register.simple_tag
def gauge(value, maximum=100, label: str = "") -> str:
    """Semicircle gauge (0..maximum) as accessible inline SVG."""
    try:
        v, m = float(value or 0), float(maximum or 1)
    except (TypeError, ValueError):
        v, m = 0.0, 1.0
    frac = max(0.0, min(1.0, v / m if m else 0))
    length = 3.14159265 * 60  # half circumference, r=60
    return format_html(
        '<svg class="gauge" viewBox="0 0 140 80" role="img" aria-label="{label}">'
        '<defs><linearGradient id="gauge-g" x1="0" x2="1"><stop offset="0" stop-color="#5b9bff"/>'
        '<stop offset="1" stop-color="#1f6fe5"/></linearGradient></defs>'
        '<path class="gauge__track" d="M10 70 A60 60 0 0 1 130 70" fill="none" stroke-width="12"'
        ' stroke-linecap="round"/>'
        '<path d="M10 70 A60 60 0 0 1 130 70" fill="none" stroke="url(#gauge-g)" stroke-width="12"'
        ' stroke-linecap="round" stroke-dasharray="{len}" stroke-dashoffset="{off}"/></svg>',
        label=label,
        len=f"{length:.1f}",
        off=f"{length * (1 - frac):.1f}",
    )


@register.simple_tag
def score_chart(days, height: int = 180) -> str:
    """Area/line chart of the average score per day (days without practice are gaps)."""
    width, pad_x, pad_top, pad_bottom = 600, 34, 12, 26
    inner_w, inner_h = width - pad_x - 8, height - pad_top - pad_bottom
    n = max(len(days) - 1, 1)

    def xy(i, score):
        return pad_x + inner_w * i / n, pad_top + inner_h * (1 - score / 100)

    points = [(i, d.avg_score) for i, d in enumerate(days) if d.avg_score is not None]
    parts = []
    for tick in (0, 50, 100):
        y = pad_top + inner_h * (1 - tick / 100)
        parts.append(
            f'<line class="chart2__grid" x1="{pad_x}" x2="{width - 8}" y1="{y:.1f}" y2="{y:.1f}"/>'
            f'<text class="chart2__tick" x="{pad_x - 8}" y="{y + 4:.1f}" text-anchor="end">'
            f"{tick}</text>"
        )
    step = max(1, len(days) // 7)
    for i, d in enumerate(days):
        if i % step == 0 or i == len(days) - 1:
            x = pad_x + inner_w * i / n
            parts.append(
                f'<text class="chart2__tick" x="{x:.1f}" y="{height - 6}" text-anchor="middle">'
                f"{d.day.day}.{d.day.month:02d}</text>"
            )
    if points:
        coords = [xy(i, s) for i, s in points]
        line = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
        base_y = pad_top + inner_h
        area = f"{coords[0][0]:.1f},{base_y} {line} {coords[-1][0]:.1f},{base_y}"
        parts.append(f'<polygon class="chart2__area" points="{area}"/>')
        parts.append(f'<polyline class="chart2__line" points="{line}"/>')
        for (x, y), (i, s) in zip(coords, points, strict=True):
            parts.append(
                f'<circle class="chart2__dot" cx="{x:.1f}" cy="{y:.1f}" r="4">'
                f"<title>{days[i].day.day}.{days[i].day.month:02d}: scor {s}%</title></circle>"
            )
    practised = [s for _, s in points]
    summary = f"Scor mediu pe zi în ultimele {len(days)} zile; " + (
        f"între {min(practised)}% și {max(practised)}%." if practised else "fără exerciții."
    )
    return mark_safe(  # noqa: S308 - built only from numbers and dates
        f'<svg class="chart2" viewBox="0 0 {width} {height}" role="img" aria-label="{summary}"'
        f' preserveAspectRatio="none"><defs><linearGradient id="chart2-g" x1="0" x2="0" y1="0"'
        f' y2="1"><stop offset="0" stop-color="#1f6fe5" stop-opacity=".28"/><stop offset="1"'
        f' stop-color="#1f6fe5" stop-opacity="0"/></linearGradient></defs>{"".join(parts)}</svg>'
    )
