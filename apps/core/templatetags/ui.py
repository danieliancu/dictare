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
        '<circle class="donut__value" cx="{h}" cy="{h}" r="{r}" stroke-width="{w}" fill="none" '
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
