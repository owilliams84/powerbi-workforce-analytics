"""The model half of the landing page, At a glance: one measure table.

Called from build_model.py after yoy_model, whose measures it leans on. The page forces a single
year, so [YoY Year], the January-to-last-snapshot window and the prior-year comparison mean here
exactly what they mean on Year on Year, and the figures the two pages share cannot drift apart.
No slicer on this page touches 'YoY Comparison', so the comparison is always the prior year.

* Stocks - headcount and every split of it - are read at the year's last month-end.
* Flows - new hires, turnover - cover the window and compare with the same months a year before;
  2019 has nothing to compare with (2018 holds August to December only) and the tiles say so.
* Engagement and the recent-hires list follow the year slicer as it stands, part months included.
* The five KPI tiles are SVG images with the icon drawn in, from etl/glance_icons.py.

Figures are checked against etl/glance_expected.py by etl/verify_glance.py.
"""

from __future__ import annotations

from pathlib import Path

from glance_icons import markup
from milestone_pbir import (
    BAD, GOLD, GOOD, INK, MUTED, NAVY, RULE, measure, measure_table_tmdl, svg_uri, tagger, write_lines,
)

tag = tagger("4b8e1d27-6c3a-4f59-9a02-e7d5c1b8f364", "glance")

ENTITY = "Glance Metrics"
M = measure
TILE_W, TILE_H = 235, 104

MONTH = 'FORMAT(DATE(2000, [YoY Last Month], 1), "mmm")'
AT_END = "CALCULATETABLE('Headcount', 'Date'[Date] = S)"


def top_one(column: str, value: str) -> str:
    """VARs naming the largest member of `column` by `value`, ties broken by name."""
    return f"""
VAR Best = TOPN(1, ADDCOLUMNS(VALUES({column}), "@v", {value}), [@v], DESC, {column}, ASC)
VAR BestName = MAXX(Best, {column})
VAR BestValue = MAXX(Best, [@v])"""


def tile(icon: str, label: str, value: str, note: str, tone: str | None = None, rising: str | None = None) -> str:
    """One 235x104 KPI tile as DAX text. label/value/note are DAX text expressions. With `tone`
    (a DAX colour) and `rising` (a DAX boolean) the note leads with a small triangle."""
    def text(x, y, size, weight, fill, body):
        return (f'"<text x=\'{x}\' y=\'{y}\' font-size=\'{size}\' font-weight=\'{weight}\' fill=\'{fill}\'>" & '
                f'{body} & "</text>"')
    frame = (f'"<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'{TILE_W}\' height=\'{TILE_H}\' '
             f'viewBox=\'0 0 {TILE_W} {TILE_H}\' font-family=\'Segoe UI, sans-serif\'>'
             f'<rect x=\'0.5\' y=\'0.5\' width=\'{TILE_W - 1}\' height=\'{TILE_H - 1}\' rx=\'4\' fill=\'#FFFFFF\' stroke=\'{RULE}\'/>'
             f'<rect width=\'3\' height=\'{TILE_H}\' fill=\'{GOLD}\'/>'
             f'<g transform=\'translate(16 32) scale(0.8333)\'>{markup(icon, NAVY, GOLD)}</g>"')
    parts = [frame, text(70, 25, 10.5, 700, MUTED, label), text(70, 60, 27, 700, INK, value)]
    if tone:
        parts.append(
            f'IF(HasComparison, "<path d=\'" & IF({rising}, "M70 87l4.5-8 4.5 8z", "M70 79l4.5 8 4.5-8z") & '
            f'"\' fill=\'" & {tone} & "\'/>", "")')
        parts.append(f'"<text x=\'" & IF(HasComparison, 84, 70) & "\' y=\'87\' font-size=\'11.5\' fill=\'{MUTED}\'>" & '
                     f'{note} & "</text>"')
    else:
        parts.append(text(70, 87, 11.5, 400, MUTED, note))
    return "\n& ".join(parts + ['"</svg>"'])


def small(text: str) -> str:
    return f'"<tspan font-size=\'14\' font-weight=\'600\' fill=\'{MUTED}\'> {text}</tspan>"'


def measures() -> list[dict]:
    no_comparison = '"no earlier year to compare with"'
    out = [
        M("Glance Rating", f"""
VAR S = [Snapshot Date]
RETURN
    AVERAGEX({AT_END}, RELATED('Employee'[Rating]))""", "0.00",
          "Mean performance rating, 1 to 5, of the people employed at the last month-end in view."),
        M("Glance Standfirst", f"""
VAR Y = [YoY Year]
VAR H = [Headcount] + 0
RETURN
    IF(H = 0, "Nobody in this selection was employed at the end of " & {MONTH} & " " & Y & ".",
        FORMAT(H, "#,0") & IF(H = 1, " person", " people") & " at the end of " & {MONTH} & " " & Y
        & ". Counts are read at the year's last month-end; hires and turnover cover " & [YoY Span]
        & IF([YoY Comparison Available], " and compare with the same months of " & (Y - 1) & ".",
             ". " & (Y - 1) & " has no figures for those months to compare with."))""", None,
          "The paragraph under the page title."),
    ]

    # ---- the five tiles ----------------------------------------------------------------------
    out.append(M("Glance Tile Headcount", f"""
VAR Y = [YoY Year]
VAR A = [YoY Headcount] + 0
VAR B = [YoY Headcount Comparison] + 0
VAR HasComparison = [YoY Comparison Available] && B > 0
VAR P = DIVIDE(A - B, B)
VAR Svg =
{tile("headcount", f'"HEADCOUNT, END " & UPPER({MONTH}) & " " & Y', 'FORMAT(A, "#,0")',
      f'IF(HasComparison, FORMAT(ABS(P), "0.0%") & " on " & {MONTH} & " " & (Y - 1) & " (" & FORMAT(B, "#,0") & ")", {no_comparison})',
      f'IF(P >= 0, "{GOOD}", "{BAD}")', "P >= 0")}
RETURN
    {svg_uri()}""", None, "KPI tile: headcount at the window's end against the same month-end a year before.",
                 category="ImageUrl"))

    out.append(M("Glance Tile Hires", f"""
VAR Y = [YoY Year]
VAR A = [YoY Joiners] + 0
VAR B = [YoY Joiners Comparison] + 0
VAR HasComparison = [YoY Comparison Available] && B > 0
VAR P = DIVIDE(A - B, B)
VAR Svg =
{tile("hires", '"NEW HIRES, " & UPPER([YoY Span])', 'FORMAT(A, "#,0")',
      f'IF(HasComparison, FORMAT(ABS(P), "0.0%") & " on " & (Y - 1) & " (" & FORMAT(B, "#,0") & ")", {no_comparison})',
      f'IF(P >= 0, "{GOOD}", "{BAD}")', "P >= 0")}
RETURN
    {svg_uri()}""", None, "KPI tile: joiners in the window against the same months a year before.",
                 category="ImageUrl"))

    out.append(M("Glance Tile Turnover", f"""
VAR Y = [YoY Year]
VAR A = [YoY Turnover]
VAR B = [YoY Turnover Comparison]
VAR HasComparison = [YoY Comparison Available] && NOT ISBLANK(B)
VAR Moved = (A - B) * 100
VAR Svg =
{tile("turnover", '"TURNOVER, ANNUALISED"', 'IF(ISBLANK(A), "n/a", FORMAT(A, "0.0%"))',
      f'IF(HasComparison, FORMAT(ABS(Moved), "0.0") & "pp on " & (Y - 1) & " (" & FORMAT(B, "0.0%") & ")", {no_comparison})',
      f'IF(Moved > 0, "{BAD}", "{GOOD}")', "Moved > 0")}
RETURN
    {svg_uri()}""", None, "KPI tile: annualised turnover over the window. A rise is bad, so it is the red one.",
                 category="ImageUrl"))

    out.append(M("Glance Tile Engagement", f"""
VAR Y = [YoY Year]
VAR A = [Engagement Score]
VAR N = [Surveys] + 0
VAR Svg =
{tile("engagement", '"ENGAGEMENT SCORE"', f'IF(ISBLANK(A), "n/a", FORMAT(A, "0.00") & {small("/ 5")})',
      'IF(N = 0, "no survey was run in " & Y, FORMAT(N, "#,0") & " survey responses in " & Y)')}
RETURN
    {svg_uri()}""", None, "KPI tile: mean engagement from surveys answered while employed. The survey ran from\n"
                          "October 2022, so earlier years have none.", category="ImageUrl"))

    out.append(M("Glance Tile Rating", f"""
VAR A = [Glance Rating]
VAR Svg =
{tile("rating", '"AVG PERFORMANCE RATING"', f'IF(ISBLANK(A), "n/a", FORMAT(A, "0.00") & {small("/ 5")})',
      f'"people employed at end " & {MONTH}')}
RETURN
    {svg_uri()}""", None, "KPI tile: mean rating of the people employed at the last month-end.", category="ImageUrl"))

    # ---- chart titles: each says what the chart shows under the current slicers ---------------
    nobody = 'IF([Headcount] + 0 = 0, "Nobody employed in this selection", '
    out += [
        M("Glance Title Department", f"""{top_one("'Employee'[Department]", "[Headcount]")}
RETURN
    {nobody}BestName & " holds " & FORMAT(DIVIDE(BestValue, [Headcount]), "0%") & " of the headcount")""", None),
        M("Glance Title Gender", f"""
VAR F = CALCULATE([Headcount], KEEPFILTERS('Employee'[Gender] = "Female")) + 0
RETURN
    {nobody}FORMAT(DIVIDE(F, [Headcount]), "0%") & " of the workforce is female")""", None),
        M("Glance Title Unit", f"""{top_one("'Employee'[Business Unit]", "[Headcount]")}
RETURN
    {nobody}BestName & " is the largest business unit, " & FORMAT(BestValue, "#,0") & " people")""", None),
        M("Glance Title Line", f"""
VAR Y = [YoY Year]
VAR A = [YoY Headcount] + 0
VAR B = [YoY Headcount Comparison] + 0
RETURN
    IF([YoY Comparison Available] && B > 0,
        "Headcount is " & IF(A >= B, "up ", "down ") & FORMAT(ABS(DIVIDE(A - B, B)), "0.0%") & " on " & {MONTH} & " " & (Y - 1),
        "Headcount at each month-end of " & Y)""", None),
        M("Glance Subtitle Line", """
VAR Y = [YoY Year]
RETURN
    IF([YoY Comparison Available], "Month-end headcount, " & Y & " against " & (Y - 1) & " (dashed)",
        "Month-end headcount; " & (Y - 1) & " has no figures for these months")""", None),
        M("Glance Title Type", f"""{top_one("'Employee'[Employee Type]", "[Headcount]")}
RETURN
    {nobody}BestName & " is the largest group at " & FORMAT(DIVIDE(BestValue, [Headcount]), "0%"))""", None),
        M("Glance Title Roles", f"""{top_one("'Employee'[Title]", "[Headcount]")}
RETURN
    {nobody}BestName & " is the largest role")""", None),
        M("Glance Title Hires", '"The last five people to join in " & [YoY Year]', None),
        M("Glance Title Turnover", f"""{top_one("'Employee'[Department]", "[YoY Turnover]")}
RETURN
    IF(ISBLANK(BestValue), "Nobody left in this selection",
        "Turnover is highest in " & BestName & ", " & FORMAT(BestValue, "0%"))""", None),
        M("Glance Subtitle Turnover", '"Annualised turnover by department, " & [YoY Span] & " " & [YoY Year]', None),
        M("Glance Title Performance", f"""{top_one("'Employee'[Performance]", "[Headcount]")}
RETURN
    {nobody}FORMAT(DIVIDE(BestValue, [Headcount]), "0%") & " are rated " & BestName)""", None),
    ]

    # ---- the recent-hires table ----------------------------------------------------------------
    out += [
        M("Glance Hire Joined", """CALCULATE(MAX('Movement'[Date]), KEEPFILTERS('Movement'[Movement] = "Joiner"))""",
          "d mmm yyyy", "The join date of the employee on the row, when it falls in the year on screen."),
        M("Glance Hire Order", """
VAR D = [Glance Hire Joined]
RETURN
    IF(NOT ISBLANK(D), INT(D) * 10000 + MAX('Employee'[Employee]))""", "0",
          "What the table's Top 5 filter orders by: join date, then employee number, so ties cannot\n"
          "let a sixth row in."),
        M("Glance Hire Department", "IF(NOT ISBLANK([Glance Hire Joined]), SELECTEDVALUE('Employee'[Department]))", None),
        M("Glance Hire Role", "IF(NOT ISBLANK([Glance Hire Joined]), SELECTEDVALUE('Employee'[Title]))", None),
    ]
    return out


def write(tables: Path) -> list[str]:
    """Write the measure table into `tables`; return the table names for model.tmdl."""
    specs = measures()
    write_lines(tables / f"{ENTITY}.tmdl", measure_table_tmdl(
        ENTITY, specs, tag, "Measures behind the landing page, At a glance. Generated by etl/glance_model.py - edit that, not this."))
    print(f"  {ENTITY}: {len(specs)} measures")
    return [ENTITY]
