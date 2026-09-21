"""Outline icons for the landing page, At a glance: five for the KPI tiles, six for the page rail.

Drawn on a 48-unit grid with a 2.8 stroke. Each icon is two groups of SVG markup: the line work,
and the one part that carries the meaning, which takes the accent colour. The same markup goes
three places - the HTML mockup, the DAX that draws the KPI tiles, and the SVG files the rail
registers - so it uses single quotes throughout and nothing DAX or a data URI would trip on.
"""

from __future__ import annotations

PERSON = "<circle cx='{x}' cy='{y}' r='{r}'/><path d='M{x0} {b}c0-{h} {w}-{h} {w} 0'/>"


def person(x: float, y: float, r: float = 6.5, w: float = 22, h: float = 13, b: float = 40) -> str:
    return PERSON.format(x=x, y=y, r=r, x0=x - w / 2, w=w, h=h, b=b)


ICONS: dict[str, tuple[str, str]] = {
    # ---- KPI tiles -----------------------------------------------------------------------
    "headcount": (person(24, 15), person(9, 20, 4.5, 14, 9, 38) + person(39, 20, 4.5, 14, 9, 38)),
    "hires": (person(19, 15, 7, 26, 15, 41), "<path d='M38 8v14M31 15h14'/>"),
    "turnover": ("<path d='M26 6H8v36h18'/>" + "<circle cx='20' cy='24' r='1.6'/>",
                 "<path d='M22 24h20M35 17l7 7-7 7'/>"),
    "engagement": ("<path d='M24 41S6 30 6 18a9.5 9.5 0 0 1 18-4 9.5 9.5 0 0 1 18 4c0 12-18 23-18 23z'/>",
                   "<path d='M13 24h6l3-6 5 11 3-5h5'/>"),
    "rating": ("<path d='M24 5l5.9 12 13.1 1.9-9.5 9.3 2.2 13.1L24 35.1l-11.7 6.2 2.2-13.1L5 18.9 18.1 17z'/>",
               "<path d='M18 25l4.5 4.5 8-9'/>"),
    # ---- page rail -----------------------------------------------------------------------
    "nav-glance": ("<rect x='6' y='6' width='15' height='15' rx='2'/><rect x='27' y='6' width='15' height='15' rx='2'/>"
                   "<rect x='6' y='27' width='15' height='15' rx='2'/>", "<rect x='27' y='27' width='15' height='15' rx='2'/>"),
    "nav-overview": ("<path d='M6 6v36h36'/>", "<path d='M12 32l9-10 7 6 12-15'/>"),
    "nav-attrition": ("<path d='M26 6H8v36h18'/>", "<path d='M20 24h22M35 17l7 7-7 7'/>"),
    "nav-engagement": ("<path d='M24 41S6 30 6 18a9.5 9.5 0 0 1 18-4 9.5 9.5 0 0 1 18 4c0 12-18 23-18 23z'/>", ""),
    "nav-quality": ("<path d='M24 5l16 6v12c0 10-7 17-16 20C15 40 8 33 8 23V11z'/>", "<path d='M17 24l5 5 9-10'/>"),
    "nav-yoy": ("<rect x='6' y='9' width='36' height='33' rx='3'/><path d='M6 18h36M15 5v8M33 5v8'/>",
                "<path d='M15 34l6-6 5 4 7-8'/>"),
}


def markup(name: str, stroke: str, accent: str) -> str:
    """The icon's two groups, ready to sit inside any <svg> or a translated/scaled <g>."""
    lines, mark = ICONS[name]
    return (f"<g fill='none' stroke-width='2.8' stroke-linecap='round' stroke-linejoin='round'>"
            f"<g stroke='{stroke}'>{lines}</g><g stroke='{accent}'>{mark}</g></g>")


def svg_file(name: str, stroke: str, accent: str) -> str:
    return f"<svg viewBox='0 0 48 48' xmlns='http://www.w3.org/2000/svg'>{markup(name, stroke, accent)}</svg>\n"
