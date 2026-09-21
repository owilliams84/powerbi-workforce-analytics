"""The model half of page 05, Year on Year: a measure table and three toggle tables.

Called from build_model.py, which rewrites the whole definition folder, so these files are
written fresh every run and their names returned for model.tmdl's `ref table` lines.

Conventions the measures rely on:

* "The same months" are the month-ends the chosen year has a headcount snapshot for: January to
  December for 2019-2022, January to July for 2023. The window is read from every employee
  (REMOVEFILTERS on Employee), so the filter panel narrows people, never the calendar.
* A comparison exists only when the earlier year has a snapshot for every month in the window.
  2018 holds August to December, so 2019 against the prior year, and 2020 against two years
  back, have nothing to compare with.
* The comparison replaces only the Year filter, so a month on a chart axis still applies.
* A rise in leavers or turnover is bad: those measures use higher_is_better=False for colour.
* Department is never on a slicer and its table has no measure filter, so its pool uses
  ALLSELECTED. Division sits in a Top/Bottom table with a measure filter, so its pool uses ALL.
  Neither column is on the filter panel (Business Unit, Employee Type), which ALL would ignore.

Figures are checked against etl/yoy_expected.py by etl/verify_yoy.ps1.
"""

from __future__ import annotations

from pathlib import Path

from milestone_pbir import (
    INK, NAVY, RULE, SLATE, card, disconnected_table_tmdl, diverging_bar, empty_card, indent,
    measure, measure_table_tmdl, pct, pp, rank_measure, ring, svg_uri, tagger, tone, write_lines,
)

tag = tagger("7d4c2b91-3e5f-4a80-b6d7-1c9e8f2a5b36", "yoy")

TOP_N = 8
ENTITY = "YoY Metrics"
M = measure

WINDOW = "KEEPFILTERS('Date'[Month No] >= F && 'Date'[Month No] <= L)"
DEPT_POOL = ("FILTER(ALLSELECTED('Employee'[Department]), "
             "[YoY Average Headcount] > 0 || [YoY Average Headcount Comparison] > 0)")
DIV_POOL = ("FILTER(ALL('Employee'[Division]), "
            "NOT ISBLANK([YoY Leavers]) || NOT ISBLANK([YoY Leavers Comparison]))")


def this_period(expr: str) -> str:
    return f"""
VAR F = [YoY First Month]
VAR L = [YoY Last Month]
RETURN
    CALCULATE({expr}, {WINDOW})"""


def comparison_period(expr: str) -> str:
    return f"""
VAR CY = [YoY Comparison Year]
VAR F = [YoY First Month]
VAR L = [YoY Last Month]
RETURN
    IF([YoY Comparison Available], CALCULATE({expr}, 'Date'[Year] = CY, {WINDOW}))"""


def snapshot_month(year: str, fn: str) -> str:
    """First or last month (1-12) with a headcount snapshot in `year`, over every employee."""
    return (f"VAR D = CALCULATE({fn}('Headcount'[Date]), REMOVEFILTERS('Employee'), REMOVEFILTERS('Date'), "
            f"'Date'[Year] = {year})")


def count(expr: str) -> str:
    """'1,234'."""
    return f'FORMAT({expr}, "#,0")'


def signed(expr: str) -> str:
    """'+79' / '-2', with the minus as an entity so SVG text stays ASCII."""
    return f'IF({expr} < 0, "&#8722;", "+") & FORMAT(ABS({expr}), "#,0")'


def points(expr: str) -> str:
    """A ratio change as '+37.7pp'."""
    return f'IF({expr} < 0, "&#8722;", "+") & FORMAT(ABS({expr}) * 100, "0.0") & "pp"'


def measures() -> list[dict]:
    out = [
        # ---- the window and whether a comparison exists -------------------------------------
        M("YoY Year", "MAX('Date'[Year])", "0", "The year on screen; the page forces a single year."),
        M("YoY Choice", "SELECTEDVALUE('YoY Comparison'[Comparison], \"Prior year\")", None),
        M("YoY Comparison Year", "[YoY Year] - IF([YoY Choice] = \"Two years back\", 2, 1)", "0"),
        M("YoY First Month", f"""
VAR Y = [YoY Year]
{snapshot_month("Y", "MIN")}
RETURN IF(NOT ISBLANK(D), MONTH(D))""", "0",
          "First month-end with a snapshot in the year on screen. MONTH(BLANK()) is 12, hence the guard."),
        M("YoY Last Month", f"""
VAR Y = [YoY Year]
{snapshot_month("Y", "MAX")}
RETURN IF(NOT ISBLANK(D), MONTH(D))""", "0", "Last month-end with a snapshot: 7 for 2023, 12 otherwise."),
        M("YoY Comparison Available", f"""
VAR CY = [YoY Comparison Year]
VAR F = [YoY First Month]
VAR L = [YoY Last Month]
{snapshot_month("CY", "MIN")}
VAR E = CALCULATE(MAX('Headcount'[Date]), REMOVEFILTERS('Employee'), REMOVEFILTERS('Date'), 'Date'[Year] = CY)
RETURN NOT ISBLANK(D) && MONTH(D) <= F && MONTH(E) >= L""", None,
          "True when the comparison year has a snapshot for every month in the window."),
        M("YoY Span", "FORMAT(DATE(2000, [YoY First Month], 1), \"mmm\") & \"-\" & FORMAT(DATE(2000, [YoY Last Month], 1), \"mmm\")",
          None, "'Jan-Jul': the window, short."),
    ]

    # ---- the period and its comparison, for every base figure ------------------------------
    base = {
        "Headcount": ("[Headcount]", "#,0", "People employed at the window's last month-end."),
        "Joiners": ("[Joiners]", "#,0", None),
        "Leavers": ("[Leavers]", "#,0", None),
        "Early Leavers": ("[Early Leavers]", "#,0", "Leavers who went inside their first year."),
        "Average Headcount": ("[Average Headcount]", "#,0.0", "Mean of the window's month-ends; 0 rather than blank for a group with nobody."),
        "Months": ("[Months in View]", "0", None),
    }
    for name, (expr, fmt, d) in base.items():
        out.append(M(f"YoY {name}", this_period(expr), fmt, d))
        out.append(M(f"YoY {name} Comparison", comparison_period(expr), fmt,
                     "The same months of the comparison year; blank when there is none." if name == "Headcount" else None))

    out += [
        M("YoY Turnover", "DIVIDE(([YoY Leavers] + 0) * 12, [YoY Average Headcount] * [YoY Months])", "0.0%",
          "Annualised over the window. Differs from page 01's 2023 figure (62.8%), which also counts\n"
          "the leavers of 1-6 August; this page compares whole months only."),
        M("YoY Turnover Comparison",
          "IF([YoY Comparison Available], DIVIDE(([YoY Leavers Comparison] + 0) * 12, [YoY Average Headcount Comparison] * [YoY Months Comparison]))",
          "0.0%"),
        M("YoY Turnover Change", "IF([YoY Comparison Available], [YoY Turnover] - [YoY Turnover Comparison])", "0.0%",
          "In ratio terms: 0.377 is 37.7 points."),
        M("YoY Turnover Change pp", "ROUND([YoY Turnover Change] * 100, 1)", "+0.0;-0.0;0.0",
          "The change in points, for the department table."),
        M("YoY Early Share", "DIVIDE([YoY Early Leavers] + 0, [YoY Leavers])", "0.0%"),
        M("YoY Early Share Comparison", "DIVIDE([YoY Early Leavers Comparison] + 0, [YoY Leavers Comparison])", "0.0%"),
        M("YoY Leaver Change", """
IF(
    [YoY Comparison Available] && (NOT ISBLANK([YoY Leavers]) || NOT ISBLANK([YoY Leavers Comparison])),
    ([YoY Leavers] + 0) - ([YoY Leavers Comparison] + 0)
)""", "+#,0;-#,0;0", "More leavers than the same months of the comparison year. A rise is bad."),

        # ---- tables ------------------------------------------------------------------------
        # Table and chart values are gated on the comparison too: with nothing to compare, the
        # empty state showed one year's figures beside blank columns (seen on the 2019 render).
        M("Dept Headcount", "IF([YoY Comparison Available], [YoY Headcount])", "#,0"),
        M("Dept Turnover", "IF([YoY Comparison Available], [YoY Turnover])", "0.0%"),
        M("Dept Leavers",
          "IF([YoY Comparison Available] && ([YoY Average Headcount] > 0 || [YoY Average Headcount Comparison] > 0), [YoY Leavers] + 0)",
          "#,0"),
        M("Dept Leavers Comparison",
          "IF([YoY Comparison Available] && ([YoY Average Headcount] > 0 || [YoY Average Headcount Comparison] > 0), [YoY Leavers Comparison] + 0)",
          "#,0"),
        M("Dept Turnover Colour", tone("[YoY Turnover Change]", higher_is_better=False), None),
        M("Departments In Play", f"IF([YoY Comparison Available], COUNTROWS({DEPT_POOL}))", "0",
          "ALLSELECTED: no measure filter on the department table narrows it."),
        M("Departments Up", f"IF([YoY Comparison Available], COUNTROWS(FILTER({DEPT_POOL}, [YoY Turnover Change] > 0)))", "0"),
        M("Dept Turnover Bar", diverging_bar(
            "[YoY Turnover Change]", f"MAXX({DEPT_POOL}, ABS([YoY Turnover Change]))",
            "NOT ISBLANK(Change) && HASONEVALUE('Employee'[Department])", higher_is_better=False), None,
          "Diverging bar for a department's change in turnover, red for a rise.", category="ImageUrl"),

        M("Division Leavers", "IF(NOT ISBLANK([Division Rank]), [YoY Leavers] + 0)", "#,0"),
        M("Division Leavers Comparison", "IF(NOT ISBLANK([Division Rank]), [YoY Leavers Comparison] + 0)", "#,0"),
        M("Divisions In Play", f"IF([YoY Comparison Available], COUNTROWS({DIV_POOL}))", "0",
          "Divisions with a leaver in either period."),
        M("Divisions Up", f"IF([YoY Comparison Available], COUNTROWS(FILTER({DIV_POOL}, [YoY Leaver Change] > 0)))", "0"),
        M("Division Name Order", """
VAR N = SELECTEDVALUE('Employee'[Division])
RETURN COUNTROWS(FILTER(ALL('Employee'[Division]), 'Employee'[Division] < N))""", "0",
          "Alphabetical position, the last tiebreak for the rank.", hidden=True),
        M("Division Rank", rank_measure(
            "'Division Ranking'[Show]", "Top", DIV_POOL,
            "(([YoY Leaver Change] * 1000 + [YoY Leavers] + 0) * 100 - [Division Name Order])",
            "HASONEVALUE('Employee'[Division]) && [YoY Comparison Available]\n"
            "            && (NOT ISBLANK([YoY Leavers]) || NOT ISBLANK([YoY Leavers Comparison]))"), "0",
          f"Position by change in leavers, from the top or the bottom as 'Division Ranking' says. Ties on\n"
          f"the change go to more leavers (Top) or fewer (Bottom), then to the name, so exactly {TOP_N}\n"
          f"rows show. The table keeps ranks 1 to {TOP_N} with\n"
          f"a visual-level filter. ALL pool: that filter narrows ALLSELECTED."),
        M("Division Change Colour", tone("[YoY Leaver Change]", higher_is_better=False), None),
        M("Division Leaver Bar", diverging_bar(
            "[YoY Leaver Change]", f"MAXX({DIV_POOL}, ABS([YoY Leaver Change]))",
            "NOT ISBLANK([Division Rank])", higher_is_better=False), None,
          "Diverging bar for a division's change in leavers, one scale for Top and Bottom.", category="ImageUrl"),

        # ---- charts ------------------------------------------------------------------------
        M("YoY Chart Choice", "SELECTEDVALUE('YoY Chart Metric'[Metric], \"Leavers\")", None),
        M("YoY Chart This",
          "IF([YoY Comparison Available], SWITCH([YoY Chart Choice], \"Headcount\", [YoY Headcount], \"Joiners\", [YoY Joiners], [YoY Leavers]))",
          "#,0"),
        M("YoY Chart Comparison",
          "SWITCH([YoY Chart Choice], \"Headcount\", [YoY Headcount Comparison], \"Joiners\", [YoY Joiners Comparison], [YoY Leavers Comparison])",
          "#,0"),
        M("YoY Chart Change", "IF([YoY Comparison Available] && NOT ISBLANK([YoY Chart This]), ([YoY Chart This] + 0) - ([YoY Chart Comparison] + 0))",
          "+#,0;-#,0;0"),
        M("YoY Chart Change Colour",
          f"IF(NOT ISBLANK([YoY Chart Change]), IF([YoY Chart Choice] = \"Leavers\", {tone('[YoY Chart Change]', higher_is_better=False)}, {tone('[YoY Chart Change]')}))",
          None, "More leavers is red; more headcount or joiners is green."),
    ]

    # ---- words that rewrite themselves -----------------------------------------------------
    out += [
        M("YoY Standfirst", """
VAR Y = [YoY Year]
VAR CY = [YoY Comparison Year]
VAR F = [YoY First Month]
VAR L = [YoY Last Month]
VAR CF = CALCULATE(MIN('Headcount'[Date]), REMOVEFILTERS('Employee'), REMOVEFILTERS('Date'), 'Date'[Year] = CY)
VAR CL = CALCULATE(MAX('Headcount'[Date]), REMOVEFILTERS('Employee'), REMOVEFILTERS('Date'), 'Date'[Year] = CY)
VAR Lv = [YoY Leavers] + 0
VAR LvC = [YoY Leavers Comparison] + 0
VAR J = [YoY Joiners] + 0
VAR JC = [YoY Joiners Comparison] + 0
VAR Opening = IF(F = 1 && L = 12, Y & " against " & CY, FORMAT(DATE(Y, F, 1), "mmmm") & " to " & FORMAT(DATE(Y, L, 1), "mmmm yyyy") & " against the same months of " & CY)
RETURN
    IF(
        NOT [YoY Comparison Available],
        Y & " has nothing to compare with: "
            & IF(ISBLANK(CF), CY & " is before the records start.", "the records hold only " & FORMAT(CF, "mmmm") & " to " & FORMAT(CL, "mmmm yyyy") & "."),
        Opening & ": leavers " & IF(Lv >= LvC, "up", "down") & " from " & FORMAT(LvC, "#,0") & " to " & FORMAT(Lv, "#,0")
            & ", joiners " & IF(J >= JC, "up", "down") & " from " & FORMAT(JC, "#,0") & " to " & FORMAT(J, "#,0")
            & ". Annualised turnover went from " & FORMAT([YoY Turnover Comparison], "0.0%") & " to " & FORMAT([YoY Turnover], "0.0%")
            & ", and headcount " & IF([YoY Headcount] >= [YoY Headcount Comparison], "rose", "fell") & " to " & FORMAT([YoY Headcount], "#,0") & "."
    )""", None, "The page's summary, or why there is nothing to compare with."),
        M("YoY Title Line Chart", "[YoY Chart Choice] & \" by month, \" & [YoY Year] & \" against \" & [YoY Comparison Year]", None),
        M("YoY Subtitle Line Chart", """
VAR Above = COUNTROWS(FILTER(VALUES('Date'[Month No]), [YoY Chart Change] > 0))
VAR Months = COUNTROWS(FILTER(VALUES('Date'[Month No]), NOT ISBLANK([YoY Chart Change])))
RETURN
    IF([YoY Comparison Available], "Above " & [YoY Comparison Year] & " in " & Above & " of " & Months & " months")""", None),
        M("YoY Title Variance Chart", "\"Which months moved \" & LOWER([YoY Chart Choice])", None),
        M("YoY Subtitle Variance Chart", """
VAR ByMonth = FILTER(ADDCOLUMNS(VALUES('Date'[Month No]), "@V", [YoY Chart Change]), NOT ISBLANK([@V]))
VAR Most = TOPN(1, ByMonth, ABS([@V]), DESC, 'Date'[Month No], ASC)
VAR V = MAXX(Most, [@V])
VAR MonthName = FORMAT(DATE(2000, MAXX(Most, 'Date'[Month No]), 1), "mmm")
RETURN
    IF(
        [YoY Comparison Available],
        [YoY Year] & " less " & [YoY Comparison Year] & ", by month: " & MonthName & " moved most ("
            & IF(V < 0, "-", "+") & FORMAT(ABS(V), "#,0") & ")"
    )""", None),
        M("YoY Title Department Table", "\"Turnover by department, \" & [YoY Year] & \" against \" & [YoY Comparison Year]", None),
        M("YoY Subtitle Department Table", f"""
VAR N = [Departments In Play]
VAR Up = [Departments Up]
VAR MostRow = TOPN(1, ADDCOLUMNS({DEPT_POOL}, "@V", [YoY Turnover Change], "@H", [YoY Headcount]), [@V], DESC, 'Employee'[Department], ASC)
VAR H = MAXX(MostRow, [@H])
RETURN
    IF(
        [YoY Comparison Available],
        "Annualised over " & [YoY Span] & "; "
            & IF(
                Up = 0,
                "down in all " & N,
                "up in " & Up & " of " & N & ", most in " & MAXX(MostRow, 'Employee'[Department])
                    & IF(H < 50, " (" & FORMAT(H + 0, "#,0") & IF(H = 1, " person)", " people)"))
            )
    )""", None, "Names the headcount when the biggest rise sits on fewer than 50 people."),
        M("YoY Title Division Table", f"""
IF(
    SELECTEDVALUE('Division Ranking'[Show], "Top") = "Top",
    "The {TOP_N} divisions where leavers rose most",
    "The {TOP_N} divisions where leavers rose least"
)""", None),
        M("YoY Subtitle Division Table",
          "IF([YoY Comparison Available], \"Leavers \" & [YoY Span] & \" \" & [YoY Year] & \" less the same months of \" & [YoY Comparison Year])",
          None),
        M("YoY Filter Summary", """
VAR Names =
    FILTER(
        {
            ("business unit", ISFILTERED('Employee'[Business Unit]), 1),
            ("employee type", ISFILTERED('Employee'[Employee Type]), 2)
        },
        [Value2]
    )
RETURN
    IF(COUNTROWS(Names) = 0, "No filters applied", "Filtered by " & CONCATENATEX(Names, [Value1], ", ", [Value3], ASC))""", None),
    ]

    # ---- the four cards --------------------------------------------------------------------
    def no_comparison(label: str) -> str:
        return empty_card(label, "Nothing to compare with for this year.")

    def ratio_ring() -> str:
        return (ring(286, 42, 26, "MAX(MIN(Ratio, 1), 0)", NAVY, "Ratio - 1")
                + f' & "<text x=\'286\' y=\'47\' font-size=\'13\' font-weight=\'700\' text-anchor=\'middle\' fill=\'{INK}\'>" & FORMAT(Ratio, "0%") & "</text>"')

    out.append(M("YoY Card Headcount", f"""
VAR Y = [YoY Year]
VAR CY = [YoY Comparison Year]
VAR MonthName = UPPER(FORMAT(DATE(2000, [YoY Last Month], 1), "mmm"))
VAR Span = [YoY Span]
VAR A = [YoY Headcount] + 0
VAR B = [YoY Headcount Comparison] + 0
VAR P = DIVIDE(A - B, B)
VAR J = [YoY Joiners] + 0
VAR JC = [YoY Joiners Comparison] + 0
VAR JP = DIVIDE(J - JC, JC)
VAR Net = J - ([YoY Leavers] + 0)
VAR Ratio = DIVIDE(A, B)
VAR Svg =
{indent(card(
    '"HEADCOUNT, END " & MonthName & " " & Y',
    count("A"),
    f'{pct("P")} & " on " & FORMAT(DATE(2000, [YoY Last Month], 1), "mmm") & " " & CY & " (" & {count("B")} & ")"',
    ('"Joiners, " & Span & " &#183; " & ' + count("J"), pct("JP"), tone("J - JC")),
    ('"Net change, " & Span', signed("Net"), tone("Net")),
    ratio_ring(),
    icon="people",
))}
VAR NoComparison = {no_comparison("HEADCOUNT")}
RETURN
    {svg_uri("IF([YoY Comparison Available], Svg, NoComparison)")}""", None,
        "Headcount at the window's end against the same month-end, joiners, and the net change.",
        category="ImageUrl"))

    out.append(M("YoY Card Leavers", f"""
VAR Y = [YoY Year]
VAR CY = [YoY Comparison Year]
VAR Span = UPPER([YoY Span])
VAR A = [YoY Leavers] + 0
VAR B = [YoY Leavers Comparison] + 0
VAR P = DIVIDE(A - B, B)
VAR ES = [YoY Early Share]
VAR ESC = [YoY Early Share Comparison]
VAR JPL = DIVIDE([YoY Joiners] + 0, A)
VAR JPLC = DIVIDE([YoY Joiners Comparison] + 0, B)
VAR Ratio = DIVIDE(A, B)
VAR Svg =
{indent(card(
    '"LEAVERS, " & Span & " " & Y',
    count("A"),
    f'{pct("P")} & " on " & CY & " (" & {count("B")} & ")"',
    ('"Left in year one &#183; " & FORMAT(ES, "0.0%")', pp("ES", "ESC"), tone("ES - ESC", higher_is_better=False)),
    ('"Joiners per leaver &#183; " & FORMAT(JPL, "0.00")', '"was " & FORMAT(JPLC, "0.00")', tone("JPL - JPLC")),
    ratio_ring(),
    icon="exit",
))}
VAR NoComparison = {no_comparison("LEAVERS")}
RETURN
    {svg_uri("IF([YoY Comparison Available], Svg, NoComparison)")}""", None,
        "Leavers against the same months, the year-one share, and joiners per leaver. The ring passes\n"
        "100% in gold when leavers rose.", category="ImageUrl"))

    out.append(M("YoY Card Turnover", f"""
VAR Y = [YoY Year]
VAR CY = [YoY Comparison Year]
VAR T = [YoY Turnover] + 0
VAR TC = [YoY Turnover Comparison] + 0
VAR Change = T - TC
VAR Depts = ADDCOLUMNS({DEPT_POOL}, "@V", [YoY Turnover Change])
VAR HighRow = TOPN(1, Depts, [@V], DESC, 'Employee'[Department], ASC)
VAR LowRow = TOPN(1, Depts, [@V], ASC, 'Employee'[Department], ASC)
VAR HighValue = MAXX(HighRow, [@V])
VAR LowValue = MAXX(LowRow, [@V])
VAR Scale = DIVIDE(116, MAX(T, TC))
VAR Bars =
    "<text x='176' y='24' font-size='9' fill='{SLATE}'>" & Y & "</text>"
        & "<rect x='204' y='16' width='" & FORMAT(T * Scale, "0.0") & "' height='10' fill='{NAVY}'/>"
        & "<text x='176' y='44' font-size='9' fill='{SLATE}'>" & CY & "</text>"
        & "<rect x='204' y='36' width='" & FORMAT(TC * Scale, "0.0") & "' height='10' fill='{SLATE}'/>"
VAR Svg =
{indent(card(
    '"TURNOVER, ANNUALISED"',
    'FORMAT(T, "0.0%")',
    f'{points("Change")} & " on " & CY & " (" & FORMAT(TC, "0.0%") & ")"',
    ('IF(HighValue > 0, "Biggest rise &#183; ", "Smallest fall &#183; ") & LEFT(MAXX(HighRow, \'Employee\'[Department]), 22)',
     points("HighValue"), tone("HighValue", higher_is_better=False)),
    ('IF(LowValue > 0, "Smallest rise &#183; ", "Biggest fall &#183; ") & LEFT(MAXX(LowRow, \'Employee\'[Department]), 22)',
     points("LowValue"), tone("LowValue", higher_is_better=False)),
    "Bars",
    icon="repeat",
))}
VAR NoComparison = {no_comparison("TURNOVER, ANNUALISED")}
RETURN
    {svg_uri("IF([YoY Comparison Available], Svg, NoComparison)")}""", None,
        "Annualised turnover in both periods as two bars, and the departments that moved most and least.",
        category="ImageUrl"))

    out.append(M("YoY Card Divisions", f"""
VAR Divisions = ADDCOLUMNS({DIV_POOL}, "@V", [YoY Leaver Change])
VAR Scale = MAXX(Divisions, ABS([@V]))
VAR UpRow = TOPN(1, Divisions, [@V], DESC, 'Employee'[Division], ASC)
VAR DownRow = TOPN(1, Divisions, [@V], ASC, 'Employee'[Division], ASC)
VAR UpValue = MAXX(UpRow, [@V])
VAR DownValue = MAXX(DownRow, [@V])
VAR Bars =
    "<line x1='176' y1='46' x2='320' y2='46' stroke='{RULE}'/>"
        & CONCATENATEX(
            Divisions,
            VAR Change = [@V]
            VAR I = COUNTROWS(FILTER(Divisions, [@V] > Change))
            VAR H = MAX(1.5, 20 * DIVIDE(ABS(Change), Scale))
            RETURN
                "<rect x='" & FORMAT(176 + I * 5.8, "0.0") & "' y='" & FORMAT(IF(Change >= 0, 46 - H, 46), "0.0")
                    & "' width='4.2' height='" & FORMAT(H, "0.0") & "' fill='" & {tone("Change", higher_is_better=False)} & "'/>",
            ""
        )
VAR Svg =
{indent(card(
    '"DIVISIONS WITH MORE LEAVERS"',
    'FORMAT([Divisions Up] + 0, "0")',
    '"of " & [Divisions In Play] & " divisions with leavers in either year"',
    ('"Most up &#183; " & LEFT(MAXX(UpRow, \'Employee\'[Division]), 24)', signed("UpValue"), tone("UpValue", higher_is_better=False)),
    ('"Most down &#183; " & LEFT(MAXX(DownRow, \'Employee\'[Division]), 24)', signed("DownValue"), tone("DownValue", higher_is_better=False)),
    "Bars",
    icon="layers",
))}
VAR NoComparison = {no_comparison("DIVISIONS WITH MORE LEAVERS")}
RETURN
    {svg_uri("IF([YoY Comparison Available], Svg, NoComparison)")}""", None,
        "Every division with a leaver in either period as a bar, from the largest rise to the largest fall.",
        category="ImageUrl"))

    return out


DISCONNECTED = {
    "YoY Comparison": (
        "Button slicer values for what page 05 compares a year with. No relationships.",
        [("Comparison", "string", "Comparison Order"), ("Comparison Order", "int64", None)],
        [("Prior year", 1), ("Two years back", 2)],
    ),
    "YoY Chart Metric": (
        "Headcount, joiners or leavers, for page 05's monthly charts.",
        [("Metric", "string", "Metric Order"), ("Metric Order", "int64", None)],
        [("Headcount", 1), ("Joiners", 2), ("Leavers", 3)],
    ),
    "Division Ranking": (
        "Top or Bottom for page 05's division table. Its own table: two toggles on one column\n"
        "cross-filter each other.",
        [("Show", "string", "Show Order"), ("Show Order", "int64", None)],
        [("Top", 1), ("Bottom", 2)],
    ),
}


def write(tables: Path) -> list[str]:
    """Write the measure table and toggle tables into `tables`; return the table names."""
    specs = measures()
    write_lines(tables / f"{ENTITY}.tmdl", measure_table_tmdl(
        ENTITY, specs, tag, "Measures behind page 05, Year on Year. Generated by etl/yoy_model.py - edit that, not this."))
    for name, (doc_text, columns, rows) in DISCONNECTED.items():
        write_lines(tables / f"{name}.tmdl", disconnected_table_tmdl(name, doc_text, columns, rows, tag))
    print(f"  {ENTITY}: {len(specs)} measures; toggle tables: {', '.join(DISCONNECTED)}")
    return [ENTITY, *DISCONNECTED]
