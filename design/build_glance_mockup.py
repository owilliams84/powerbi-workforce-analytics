"""Build design/glance-mockup.html: the landing page, At a glance, drawn at the 1440x900 canvas with the
figures from etl/glance_expected.py. Every block is tagged with the Power BI visual it becomes.

    python design/build_glance_mockup.py [year]
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "etl"))

from glance_expected import expected  # noqa: E402
from glance_icons import markup  # noqa: E402

INK, NAVY, GOLD, SLATE, LIGHT, RULE = "#0A0917", "#111F38", "#C9A227", "#7C8598", "#BCC1D2", "#E3E7EF"
MUTED, BODY, GOOD, BAD, PAPER = "#667284", "#4A5768", "#1E7A4C", "#B3261E", "#F4F6FA"
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
PAGES = [("nav-glance", "At a glance"), ("nav-overview", "Overview"), ("nav-attrition", "Attrition"),
         ("nav-engagement", "Engagement"), ("nav-quality", "Data quality"), ("nav-yoy", "Year on year")]


def icon(name: str, size: int, stroke: str = NAVY) -> str:
    return f"<svg width='{size}' height='{size}' viewBox='0 0 48 48'>{markup(name, stroke, GOLD)}</svg>"


def tile(x: int, name: str, label: str, value: str, note: str, tone: str | None = None, arrow: str = "") -> str:
    delta = f"<span style='color:{tone};font-weight:600'>{arrow} </span>" if tone else ""
    return (f"<div class='tile' style='left:{x}px'><div class='bar'></div><div class='ic'>{icon(name, 40)}</div>"
            f"<div class='lab'>{label}</div><div class='val'>{value}</div><div class='note'>{delta}{note}</div></div>")


def columns(data: dict, w: int, h: int, colour: str, fmt) -> str:
    top, n = max(data.values()), len(data)
    step = w / n
    out = []
    for i, (k, v) in enumerate(data.items()):
        bh = (h - 34) * v / top
        x = i * step + step * 0.2
        out.append(f"<rect x='{x:.1f}' y='{h - 18 - bh:.1f}' width='{step * 0.6:.1f}' height='{bh:.1f}' fill='{colour}'/>"
                   f"<text x='{x + step * 0.3:.1f}' y='{h - 22 - bh:.1f}' class='dl' text-anchor='middle'>{fmt(v)}</text>"
                   f"<text x='{x + step * 0.3:.1f}' y='{h - 4}' class='ax' text-anchor='middle'>{k}</text>")
    return f"<svg width='{w}' height='{h}'>{''.join(out)}</svg>"


def bars(data: dict, w: int, h: int, colour: str, label_w: int = 150) -> str:
    top, row = max(data.values()), h / len(data)
    out = []
    for i, (k, v) in enumerate(data.items()):
        bw = (w - label_w - 40) * v / top
        y = i * row + row * 0.18
        out.append(f"<text x='{label_w - 8}' y='{y + row * 0.45:.1f}' class='ax' text-anchor='end'>{k}</text>"
                   f"<rect x='{label_w}' y='{y:.1f}' width='{bw:.1f}' height='{row * 0.64:.1f}' fill='{colour}'/>"
                   f"<text x='{label_w + bw + 6:.1f}' y='{y + row * 0.45:.1f}' class='dl'>{v:,}</text>")
    return f"<svg width='{w}' height='{h}'>{''.join(out)}</svg>"


def donut(data: dict, colours: list[str], size: int = 120) -> str:
    total, r, c = sum(data.values()), size / 2 - 10, size / 2
    angle, arcs, legend = -math.pi / 2, [], []
    for (k, v), col in zip(data.items(), colours):
        sweep = 2 * math.pi * v / total
        x0, y0 = c + r * math.cos(angle), c + r * math.sin(angle)
        angle += sweep
        x1, y1 = c + r * math.cos(angle), c + r * math.sin(angle)
        arcs.append(f"<path d='M{x0:.2f} {y0:.2f}A{r} {r} 0 {int(sweep > math.pi)} 1 {x1:.2f} {y1:.2f}' "
                    f"stroke='{col}' stroke-width='18' fill='none'/>")
        legend.append(f"<div><i style='background:{col}'></i>{k}<b>{v:,}</b><span>{v / total:.1%}</span></div>")
    return (f"<div class='donut'><svg width='{size}' height='{size}'>{''.join(arcs)}"
            f"<text x='{c}' y='{c + 2}' text-anchor='middle' class='dn'>{total:,}</text>"
            f"<text x='{c}' y='{c + 16}' text-anchor='middle' class='ax'>people</text></svg>"
            f"<div class='legend'>{''.join(legend)}</div></div>")


def line(now: dict, was: dict, w: int, h: int) -> str:
    vals = list(now.values()) + list(was.values())
    lo, hi = min(vals) * 0.97, max(vals) * 1.02
    keys = list(now)

    def pts(d):
        return " ".join(f"{30 + i * (w - 60) / (len(keys) - 1):.1f},{8 + (h - 34) * (1 - (d[k] - lo) / (hi - lo)):.1f}"
                        for i, k in enumerate(keys) if k in d)
    ax = "".join(f"<text x='{30 + i * (w - 60) / (len(keys) - 1):.1f}' y='{h - 4}' class='ax' text-anchor='middle'>"
                 f"{MONTHS[int(k) - 1]}</text>" for i, k in enumerate(keys))
    return (f"<svg width='{w}' height='{h}'><polyline points='{pts(was)}' fill='none' stroke='{SLATE}' stroke-width='2' "
            f"stroke-dasharray='5 4'/><polyline points='{pts(now)}' fill='none' stroke='{NAVY}' stroke-width='2.5'/>{ax}</svg>")


def panel(x, y, w, h, title, sub, body, tag) -> str:
    return (f"<div class='panel' style='left:{x}px;top:{y}px;width:{w}px;height:{h}px'><span class='tag'>{tag}</span>"
            f"<h3>{title}</h3><p>{sub}</p>{body}</div>")


def build(year: int) -> str:
    d = expected(year, {})
    last = MONTHS[d["months"][1] - 1]
    span = f"{MONTHS[d['months'][0] - 1]}-{last}"
    hc = d["headcount"] / d["headcount_was"] - 1
    jn = d["joiners"] / d["joiners_was"] - 1
    tp = (d["turnover"] - d["turnover_was"]) * 100
    dept = dict(sorted(d["department"].items(), key=lambda kv: -kv[1]))
    roles = dict(sorted(d["title"].items(), key=lambda kv: -kv[1])[:5])
    units = dict(sorted(d["business_unit"].items(), key=lambda kv: -kv[1]))
    turn = {k: d["turnover_by_department"][k] for k in dept}
    perf = {k: d["performance"][k] for k in ["Exceeds", "Fully Meets", "Needs Improvement", "PIP"]}
    top_dept, top_role = next(iter(dept.items())), next(iter(roles.items()))
    short = {"Software Engineering": "Software Eng.", "Executive Office": "Executive", "Admin Offices": "Admin"}

    rail = "".join(f"<div class='nav{' on' if i == 0 else ''}'>{icon(n, 20, '#FFFFFF')}<span>{t}</span></div>"
                   for i, (n, t) in enumerate(PAGES))
    tiles = "".join([
        tile(192, "headcount", f"HEADCOUNT, END {last.upper()} {year}", f"{d['headcount']:,}",
             f"{abs(hc):.1%} on {last} {year - 1} ({d['headcount_was']:,})", GOOD if hc >= 0 else BAD, "&#9650;" if hc >= 0 else "&#9660;"),
        tile(439, "hires", f"NEW HIRES, {span.upper()}", f"{d['joiners']:,}",
             f"{abs(jn):.1%} on {year - 1} ({d['joiners_was']:,})", GOOD if jn >= 0 else BAD, "&#9650;" if jn >= 0 else "&#9660;"),
        tile(686, "turnover", "TURNOVER, ANNUALISED", f"{d['turnover']:.1%}",
             f"{abs(tp):.1f}pp on {year - 1} ({d['turnover_was']:.1%})", BAD if tp > 0 else GOOD, "&#9650;" if tp > 0 else "&#9660;"),
        tile(933, "engagement", "ENGAGEMENT SCORE", f"{d['engagement']:.2f} <small>/ 5</small>", f"{d['surveys']:,} survey responses in {year}"),
        tile(1180, "rating", "AVG PERFORMANCE RATING", f"{d['rating']:.2f} <small>/ 5</small>", f"people employed at end {last}"),
    ])
    hires = "".join(f"<tr><td>{h['employee']}</td><td>{h['department']}</td><td>{h['title']}</td><td>{h['joined']}</td></tr>"
                    for h in d["recent_hires"])
    panels = "".join([
        panel(192, 272, 476, 196, f"{top_dept[0]} holds {top_dept[1] / d['headcount']:.0%} of the headcount", "People employed at the month-end, by department",
              columns({short.get(k, k): v for k, v in dept.items()}, 452, 138, NAVY, lambda v: f"{v:,}"), "columnChart"),
        panel(680, 272, 340, 196, f"{d['gender']['Female'] / d['headcount']:.0%} of the workforce is female", "Headcount by gender",
              donut(d["gender"], [NAVY, GOLD]), "donutChart"),
        panel(1032, 272, 384, 196, "Ten business units of near-equal size", "Headcount by business unit",
              bars(units, 360, 140, SLATE, 50), "barChart"),
        panel(192, 480, 476, 196, f"Headcount fell every month of {year}", f"Month-end headcount, {year} against {year - 1} (dashed)",
              line(d["headcount_by_month"], d["headcount_by_month_was"], 452, 138), "lineChart"),
        panel(680, 480, 340, 196, "Contract and part-time make up two thirds", "Headcount by employee type",
              donut(dict(sorted(d["employee_type"].items(), key=lambda kv: -kv[1])), [NAVY, GOLD, LIGHT]), "donutChart"),
        panel(1032, 480, 384, 196, f"{top_role[0]} is the largest role", "Top five job roles by headcount",
              bars(roles, 360, 140, NAVY, 150), "barChart + TopN filter"),
        panel(192, 688, 476, 196, "Most recent hires", f"The last five people to join in {year}",
              f"<table><tr><th>Employee</th><th>Department</th><th>Job role</th><th>Joined</th></tr>{hires}</table>", "pivotTable + TopN filter"),
        panel(680, 688, 340, 196, "Turnover is highest in the smallest teams", f"Annualised turnover by department, {span} {year}",
              columns({short.get(k, k).split()[0]: v for k, v in turn.items()}, 316, 138, GOLD, lambda v: f"{v:.0%}"), "columnChart"),
        panel(1032, 688, 384, 196, f"{perf['Fully Meets'] / d['headcount']:.0%} fully meet expectations", "Headcount by performance rating",
              donut(perf, [GOLD, NAVY, SLATE, LIGHT]), "donutChart"),
    ])
    years = "".join(f"<b class='{'on' if y == year else ''}'>{y}</b>" for y in range(2019, 2024))
    drops = "".join(f"<div class='drop' style='left:{x}px'><em>{t}</em><span>All</span></div>"
                    for x, t in [(946, "DEPARTMENT"), (1106, "BUSINESS UNIT"), (1266, "JOB ROLE")])
    return f"""<!doctype html><meta charset='utf-8'><title>At a glance - mockup</title><style>
body{{margin:24px;background:#d9dce4;font-family:'Segoe UI',sans-serif}}
.stage{{position:relative;width:1440px;height:900px;background:{PAPER};overflow:hidden}}
.band{{position:absolute;inset:0 0 auto 0;height:60px;background:{INK};color:#fff;font-weight:700;font-size:20px;line-height:60px;padding-left:76px}}
.band i{{color:{GOLD};font-style:normal}} .band u{{position:absolute;right:24px;font:700 11px Consolas;letter-spacing:2px;color:{GOLD};text-decoration:none}}
.rail{{position:absolute;left:0;top:60px;width:176px;bottom:0;background:{INK}}}
.nav{{display:flex;align-items:center;gap:12px;height:44px;margin:6px 10px;padding:0 12px;border-radius:4px;color:#fff;font-size:13px;opacity:.78}}
.nav.on{{background:{NAVY};opacity:1;box-shadow:inset 3px 0 {GOLD};font-weight:600}}
.quote{{position:absolute;left:0;bottom:28px;width:176px;text-align:center;color:{LIGHT};font-size:11px;line-height:1.5}}
h1{{position:absolute;left:192px;top:66px;margin:0;font-size:29px;color:{INK}}} .stand{{position:absolute;left:192px;top:108px;width:460px;font-size:12.5px;color:{BODY};line-height:1.35}}
.years{{position:absolute;left:666px;top:72px;width:270px}} .years em,.drop em{{display:block;font:700 11px 'Segoe UI';color:{MUTED};font-style:normal;margin-bottom:6px}}
.years b{{display:inline-block;width:52px;height:38px;line-height:38px;text-align:center;border:1px solid {RULE};background:#fff;font-size:12px;color:{BODY}}} .years b.on{{background:{INK};color:#fff}}
.drop{{position:absolute;top:66px;width:130px;height:60px;background:#fff;border:1px solid {RULE};border-radius:4px;padding:8px 10px}} .drop span{{display:block;border:1px solid {RULE};padding:5px 8px;font-size:12.5px;color:{BODY}}}
.tile{{position:absolute;top:156px;width:235px;height:104px;background:#fff;border:1px solid {RULE};border-radius:4px;box-sizing:border-box;overflow:hidden}}
.tile .bar{{position:absolute;left:0;top:0;bottom:0;width:3px;background:{GOLD}}} .tile .ic{{position:absolute;left:16px;top:30px}}
.tile .lab{{position:absolute;left:70px;top:14px;font:700 10.5px 'Segoe UI';letter-spacing:.4px;color:{MUTED}}} .tile .val{{position:absolute;left:70px;top:30px;font:700 27px 'Segoe UI';color:{INK}}}
.tile small{{font-size:14px;color:{MUTED};font-weight:600}} .tile .note{{position:absolute;left:70px;top:74px;font-size:11.5px;color:{MUTED};white-space:nowrap}}
.panel{{position:absolute;background:#fff;border:1px solid {RULE};border-radius:4px;box-sizing:border-box;padding:8px 12px}} .panel h3{{margin:0;font-size:14px;color:{INK}}} .panel p{{margin:1px 0 6px;font-size:11.5px;color:{MUTED}}}
.tag{{position:absolute;right:6px;top:-9px;background:#6B3FA0;color:#fff;font:600 9px Consolas;padding:1px 5px;border-radius:2px}}
.ax{{font-size:10.5px;fill:{MUTED}}} .dl{{font-size:10.5px;fill:{BODY};font-weight:600}} .dn{{font-size:17px;font-weight:700;fill:{INK}}}
.donut{{display:flex;align-items:center;gap:14px}} .legend div{{font-size:11.5px;color:{BODY};margin:5px 0;white-space:nowrap}} .legend i{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}}
.legend b{{margin-left:10px;color:{INK}}} .legend span{{margin-left:6px;color:{MUTED}}}
table{{border-collapse:collapse;width:100%;font-size:11.5px;color:{BODY}}} th{{text-align:left;color:{MUTED};border-bottom:1px solid {INK};padding:3px 4px}} td{{padding:4px;border-bottom:1px solid {RULE}}}
</style><div class='stage'>
<div class='band'>Milestone <i>BI</i><u>01 / AT A GLANCE</u></div>
<div class='rail'>{rail}<div class='quote'>Page rail: six<br>page-navigation buttons</div></div>
<h1>Workforce at a glance</h1><div class='stand'>{d['headcount']:,} people at the end of {last} {year}. Counts are read at the year's last month-end; hires and turnover cover {span} and compare with the same months of {year - 1}.</div>
<div class='years'><em>YEAR</em>{years}</div>{drops}{tiles}{panels}</div>"""


if __name__ == "__main__":
    yr = int(sys.argv[1]) if len(sys.argv) > 1 else 2023
    out = ROOT / "design" / "glance-mockup.html"
    out.write_text(build(yr), encoding="utf-8", newline="\n")
    print(f"wrote {out}")
