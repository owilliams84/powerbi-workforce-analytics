"""Generate the PBIR report definition - five pages, the Milestone theme and every visual.

Pages 01-04 use the helpers below. Page 05 (Year on Year) lives in etl/yoy_page.py, built on the
milestone_pbir library, and adds the filter panel's bookmarks.

PBIR stores one JSON file per visual and wraps every property in the same
{"expr": {"Literal": {"Value": ...}}} envelope. Hand-editing that is how typos get in, so the
report is generated from this file: the helpers own the envelope and the page functions read as
layout.

    python etl/build_report.py

Rewrites <report>/definition/pages from scratch every run. That matters - a renamed visual left
behind on disk still renders, as an empty box.
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

import milestone_pbir
import yoy_page

ROOT = Path(__file__).resolve().parents[1]
NAME = "Workforce Analytics"
REPORT = ROOT / f"{NAME}.Report"
PAGES = REPORT / "definition" / "pages"
RESOURCES = REPORT / "StaticResources" / "RegisteredResources"
ASSETS = ROOT / "etl" / "assets"

CANVAS_W, CANVAS_H = 1440, 900

# --------------------------------------------------------------------------------------------
# Palette: milestonebi.com's own tokens.
# --------------------------------------------------------------------------------------------
PAPER = "#F4F6FA"
CARD = "#FFFFFF"
RULE = "#E3E7EF"
INK = "#0A0917"
BODY = "#4A5768"
MUTED = "#667284"
GOLD = "#C9A227"
GOLD_TEXT = "#8A6D14"
NAVY = "#111F38"
SLATE = "#7C8598"
LIGHT = "#BCC1D2"
GOOD = "#1E7A4C"
BAD = "#B3261E"

THEME_NAME = "MilestoneTheme.json"
MARK_NAME = "MilestoneMark.svg"

# --------------------------------------------------------------------------------------------
# Expression envelope helpers
# --------------------------------------------------------------------------------------------


def lit(value) -> dict:
    """Wrap a literal in the expression envelope PBIR expects.

    The suffix is load-bearing: 'D' for a double, 'L' for an integer, quotes for text. Getting
    it wrong makes Desktop drop the property silently rather than complain.
    """
    if isinstance(value, bool):
        v = "true" if value else "false"
    elif isinstance(value, int):
        v = f"{value}L"
    elif isinstance(value, float):
        v = f"{value}D"
    else:
        v = f"'{value}'"
    return {"expr": {"Literal": {"Value": v}}}


def colour(hex_code: str) -> dict:
    return {"solid": {"color": lit(hex_code)}}


def obj(**props) -> list:
    return [{"properties": props}]


def obj_for(metadata: str, **props) -> dict:
    return {"properties": props, "selector": {"metadata": metadata}}


def obj_for_value(table: str, col: str, value, **props) -> dict:
    """A property block scoped to one category value."""
    return {"properties": props, "selector": {"data": [{"scopeId": {"Comparison": {
        "ComparisonKind": 0,
        "Left": {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": col}},
        "Right": lit(value)["expr"],
    }}}]}}


def measure(table: str, name: str, display: str | None = None) -> dict:
    field = {
        "field": {"Measure": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}},
        "queryRef": f"{table}.{name}",
        "nativeQueryRef": name,
    }
    if display:
        field["displayName"] = display
    return field


def column(table: str, name: str, display: str | None = None, active: bool = True) -> dict:
    field = {
        "field": {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}},
        "queryRef": f"{table}.{name}",
        "nativeQueryRef": name,
    }
    if active:
        field["active"] = True
    if display:
        field["displayName"] = display
    return field


def m(name: str, display: str | None = None) -> dict:
    return measure("Metrics", name, display)


def sort_by(field: dict, direction: str = "Descending") -> dict:
    return {"sort": [{"field": field["field"], "direction": direction}], "isDefaultSort": True}


def categorical_filter(name: str, table: str, col: str, values: list, alias: str = "t") -> dict:
    """A visual-level 'this column is one of these values' filter."""
    return {
        "name": name,
        "field": {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": col}},
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": alias, "Entity": table, "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": alias}},
                                            "Property": col}}],
                "Values": [[lit(v)["expr"]] for v in values],
            }}}],
        },
    }


# --------------------------------------------------------------------------------------------
# Container chrome
# --------------------------------------------------------------------------------------------


def chrome(title: str | None = None, subtitle: str | None = None, *,
           transparent: bool = False) -> dict:
    """Card background, hairline border and the small bold title every panel shares.

    subtitle is the second positional parameter and transparent is keyword-only: with them the
    other way round, chrome("Title", "Subtitle") put the caption into transparent and dropped it.
    """
    show = not transparent
    out = {
        "padding": obj(top=lit(8.0), bottom=lit(8.0), left=lit(10.0), right=lit(10.0)),
        "dropShadow": obj(show=lit(False)),
        "background": obj(show=lit(show), color=colour(CARD), transparency=lit(0.0)),
        "border": obj(show=lit(show), color=colour(RULE), radius=lit(4)),
    }
    if title:
        out["title"] = obj(show=lit(True), text=lit(title), fontSize=lit(10.5), bold=lit(True),
                           fontColor=colour(INK), heading=lit("Heading3"))
        if subtitle:
            out["subTitle"] = obj(show=lit(True), text=lit(subtitle), fontSize=lit(8.5),
                                  fontColor=colour(MUTED))
    else:
        out["title"] = obj(show=lit(False))
    return out


def visual(name: str, vtype: str, x: int, y: int, w: int, h: int, z: int,
           query: dict | None = None, objects: dict | None = None,
           container: dict | None = None, filters: list | None = None) -> dict:
    node: dict = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.5.0/schema.json",
        "name": name,
        "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z},
        "visual": {"visualType": vtype},
    }
    if query is not None:
        node["visual"]["query"] = query
    if objects:
        node["visual"]["objects"] = objects
    node["visual"]["visualContainerObjects"] = container or chrome()
    if filters:
        # filterConfig is a sibling of "visual" at the root, not a child of it.
        node["filterConfig"] = {"filters": filters}
    return node


# --------------------------------------------------------------------------------------------
# Reusable formatting blocks
# --------------------------------------------------------------------------------------------


def axis(show_title: bool = False, gridlines: bool = False, size: float = 8.5, **extra) -> list:
    return [{"properties": {
        "show": lit(True), "showAxisTitle": lit(show_title), "fontSize": lit(size),
        "labelColor": colour(MUTED), "gridlineShow": lit(gridlines),
        **({"gridlineColor": colour(RULE)} if gridlines else {}),
        **extra,
    }}]


def legend(show: bool = True, position: str = "Top") -> list:
    return [{"properties": {
        "show": lit(show), "position": lit(position), "showTitle": lit(False),
        "fontSize": lit(8.5), "labelColor": colour(MUTED),
    }}]


def no_labels() -> list:
    return [{"properties": {"show": lit(False)}}]


def data_labels(size: float = 8.5, units: str = "1", colour_hex: str = BODY) -> list:
    return [{"properties": {
        "show": lit(True), "fontSize": lit(size), "color": colour(colour_hex),
        "labelDisplayUnits": lit(units),
    }}]


def series_colour(mapping: dict[str, str]) -> list:
    return [obj_for(k, fill=colour(v)) for k, v in mapping.items()]


def value_colours(table: str, col: str, mapping: dict) -> list:
    return [obj_for_value(table, col, k, fill=colour(v)) for k, v in mapping.items()]


def line_style() -> list:
    return [{"properties": {
        "strokeWidth": lit(2), "lineStyle": lit("solid"), "showMarker": lit(False),
    }}]


def no_chrome() -> dict:
    return {
        "padding": obj(top=lit(0.0), bottom=lit(0.0), left=lit(0.0), right=lit(0.0)),
        "dropShadow": obj(show=lit(False)),
        "background": obj(show=lit(False)),
        "border": obj(show=lit(False)),
        "title": obj(show=lit(False)),
    }


def textbox(name: str, x: int, y: int, w: int, h: int, z: int, paragraphs: list,
            background: str | None = None) -> dict:
    """paragraphs: each is a list of runs, or a single run dict for a one-run paragraph."""
    out = []
    for para in paragraphs:
        runs = para if isinstance(para, list) else [para]
        text_runs = []
        for run in runs:
            style = {"fontSize": f"{run.get('size', 11)}pt", "color": run.get("color", BODY)}
            if run.get("bold"):
                style["fontWeight"] = "bold"
            if run.get("family"):
                style["fontFamily"] = run["family"]
            if run.get("spacing"):
                style["letterSpacing"] = run["spacing"]
            text_runs.append({"value": run["text"], "textStyle": style})
        node = {"textRuns": text_runs}
        if runs[0].get("align"):
            node["horizontalTextAlignment"] = runs[0]["align"]
        out.append(node)
    container = no_chrome()
    if background:
        container["background"] = obj(show=lit(True), color=colour(background),
                                      transparency=lit(0.0))
        container["padding"] = obj(top=lit(4.0), bottom=lit(4.0), left=lit(10.0),
                                   right=lit(10.0))
    node = visual(name, "textbox", x, y, w, h, z, container=container)
    node["visual"]["objects"] = {"general": [{"properties": {"paragraphs": out}}]}
    return node


def note(name: str, x: int, y: int, w: int, h: int, z: int, heading: str,
         lines: list[str]) -> dict:
    """A card of prose - used where the honest caveat needs more room than a subtitle."""
    paras: list = [[{"text": heading, "size": 10.5, "color": INK, "bold": True}]]
    for line in lines:
        paras.append([{"text": "", "size": 4, "color": BODY}])
        paras.append([{"text": line, "size": 9, "color": BODY}])
    node = textbox(name, x, y, w, h, z, paras)
    node["visual"]["visualContainerObjects"] = chrome()
    return node


def image(name: str, x: int, y: int, w: int, h: int, z: int, resource: str) -> dict:
    node = visual(name, "image", x, y, w, h, z, container=no_chrome())
    node["visual"]["objects"] = {
        "general": [{"properties": {"imageUrl": {"expr": {"ResourcePackageItem": {
            "PackageName": "RegisteredResources", "PackageType": 1, "ItemName": resource}}}}}],
        "imageScaling": [{"properties": {"imageScalingType": lit("Fit")}}],
    }
    return node


def kpi_card(name: str, x: int, y: int, w: int, h: int, z: int, measures: list[dict],
             filters: list | None = None, value_size: float = 17.0) -> dict:
    return visual(
        name, "cardVisual", x, y, w, h, z,
        query={"queryState": {"Data": {"projections": measures}}},
        objects={
            "general": [{"properties": {}}],
            "value": [{"properties": {
                "fontSize": lit(value_size), "bold": lit(True), "fontColor": colour(INK),
                "fontFamily": lit("Segoe UI"), "horizontalAlignment": lit("Left"),
                # Without this the auto units turn 1,480 into "1K".
                "labelDisplayUnits": lit("1"),
            }, "selector": {"id": "default"}}],
            "label": [{"properties": {
                "show": lit(True), "fontSize": lit(8.5), "fontColor": colour(MUTED),
                "bold": lit(False), "position": lit("belowValue"),
                "horizontalAlignment": lit("Left"),
            }, "selector": {"id": "default"}}],
            "accentBar": [{"properties": {
                "show": lit(True), "color": colour(GOLD), "width": lit(3),
            }, "selector": {"id": "default"}}],
        },
        filters=filters,
    )


def slicer(name: str, x: int, y: int, w: int, h: int, z: int, table: str, col: str,
           header: str, mode: str = "Dropdown") -> dict:
    return visual(
        name, "slicer", x, y, w, h, z,
        query={"queryState": {"Values": {"projections": [column(table, col)]}}},
        objects={
            "general": [{"properties": {"orientation": lit(0)}}],
            "data": [{"properties": {"mode": lit(mode)}}],
            "header": [{"properties": {
                "show": lit(True), "text": lit(header), "textSize": lit(8.5),
                "fontColor": colour(MUTED), "bold": lit(True),
            }}],
            "items": [{"properties": {
                "fontColor": colour(BODY), "textSize": lit(9.5), "background": colour(CARD),
            }}],
        },
    )


def table_visual(name: str, x: int, y: int, w: int, h: int, z: int, fields: list[dict],
                 sort: dict | None, title: str, subtitle: str | None = None,
                 filters: list | None = None, totals: bool = False,
                 columns: list[dict] | None = None) -> dict:
    """A flat ranked table, or with columns= a cross-tab. Built as a matrix: on Desktop 2.157 a
    tableEx generated this way rendered the column fields and silently dropped every measure."""
    rows = [f for f in fields if "Column" in f["field"]]
    values = [f for f in fields if "Measure" in f["field"]]
    state = {"Rows": {"projections": rows}, "Values": {"projections": values}}
    if columns:
        state["Columns"] = {"projections": columns}
    query: dict = {"queryState": state}
    if sort:
        query["sortDefinition"] = sort
    return visual(
        name, "pivotTable", x, y, w, h, z,
        query=query,
        objects={
            "grid": [{"properties": {
                "gridVertical": lit(False), "gridHorizontal": lit(True),
                "gridHorizontalColor": colour(RULE), "rowPadding": lit(3),
            }}],
            "columnHeaders": [{"properties": {
                "fontSize": lit(9.0), "bold": lit(True), "fontColor": colour(INK),
                "backColor": colour(CARD), "alignment": lit("Right"),
            }}],
            "rowHeaders": [{"properties": {
                "fontSize": lit(9.0), "fontColor": colour(BODY), "backColor": colour(CARD),
            }}],
            "values": [{"properties": {
                "fontSize": lit(9.0), "fontColorPrimary": colour(BODY),
                "backColorPrimary": colour(CARD), "backColorSecondary": colour(CARD),
            }}],
            "subTotals": [{"properties": {"rowSubtotals": lit(totals),
                                          "columnSubtotals": lit(totals)}}],
        },
        container=chrome(title, subtitle=subtitle),
        filters=filters,
    )


def chart(name: str, vtype: str, x: int, y: int, w: int, h: int, z: int, category: dict,
          values: list[dict], title: str, subtitle: str | None = None, *,
          series: dict | None = None, tooltips: list[dict] | None = None,
          sort: dict | None = None, colours: list | None = None, labels: list | None = None,
          show_legend: bool = False, filters: list | None = None) -> dict:
    state: dict = {"Category": {"projections": [category]}, "Y": {"projections": values}}
    if series:
        state["Series"] = {"projections": [series]}
    if tooltips:
        state["Tooltips"] = {"projections": tooltips}
    objects: dict = {
        "categoryAxis": axis(), "valueAxis": axis(gridlines=True),
        "legend": legend(show_legend), "labels": labels or no_labels(),
    }
    if vtype == "lineChart":
        objects["lineStyles"] = line_style()
    if colours:
        objects["dataPoint"] = colours
    query: dict = {"queryState": state}
    if sort:
        query["sortDefinition"] = sort
    return visual(name, vtype, x, y, w, h, z, query=query, objects=objects,
                  container=chrome(title, subtitle), filters=filters)


# --------------------------------------------------------------------------------------------
# Masthead
# --------------------------------------------------------------------------------------------


def masthead(slug: str, title: str, standfirst: str, ref: str) -> list[dict]:
    return [
        textbox(f"vBand{slug}", 0, 0, CANVAS_W, 60, 50, [
            [{"text": "", "size": 6, "color": INK}],
        ], background=INK),
        image(f"vMark{slug}", 24, 12, 44, 38, 60, MARK_NAME),
        textbox(f"vWordmark{slug}", 76, 15, 260, 32, 70, [
            [{"text": "Milestone ", "size": 15, "color": CARD, "bold": True},
             {"text": "BI", "size": 15, "color": GOLD, "bold": True}],
        ]),
        textbox(f"vRef{slug}", 1016, 22, 400, 22, 80, [
            [{"text": ref, "size": 8, "color": GOLD, "bold": True, "family": "Consolas",
              "spacing": "2px", "align": "right"}],
        ]),
        textbox(f"vTitle{slug}", 24, 74, 1000, 40, 90, [
            [{"text": title, "size": 22, "color": INK, "bold": True}],
        ]),
        textbox(f"vStand{slug}", 24, 114, 1030, 46, 95, [
            [{"text": standfirst, "size": 10, "color": BODY}],
        ]),
    ]


def page(name: str, display: str) -> dict:
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
        "name": name,
        "displayName": display,
        "displayOption": "FitToPage",
        "height": CANVAS_H,
        "width": CANVAS_W,
        "objects": {
            "background": obj(color=colour(PAPER), transparency=lit(0.0)),
            "displayArea": obj(verticalAlignment=lit("Top")),
        },
    }


GROUP_COLOURS = {"Voluntary": GOLD, "Involuntary": NAVY, "Retirement": LIGHT}
STATUS_COLOURS = {"Employed": NAVY, "Left": GOLD}

SL_Y, SL_H = 74, 84
SL1_X, SL2_X, SL_W = 1076, 1246, 170


def year_controls(slug: str) -> list[dict]:
    return [
        slicer(f"vYear{slug}", SL1_X, SL_Y, SL_W, SL_H, 400, "Date", "Year", "YEAR"),
        kpi_card(f"vPeriod{slug}", SL2_X, SL_Y, SL_W, SL_H, 410,
                 [m("Report Period", "Figures for")], value_size=11.0),
    ]


# --------------------------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------------------------


def page_overview() -> tuple[dict, list[dict]]:
    v: list[dict] = []
    v += masthead(
        "Ovr",
        "Workforce, August 2018 to August 2023",
        "3,000 people over five years, 1,533 of whom have left. Employed or left is decided by "
        "each person's own start and exit dates - the HR system's status field contradicts "
        "them for 1,146 people. Every figure follows the year slicer.",
        "01 / OVERVIEW",
    )
    v += year_controls("Ovr")

    v.append(kpi_card("vKpiOvr", 24, 176, 1392, 92, 500, [
        m("Headcount", "Headcount at period end"),
        m("Joiners", "Joiners"),
        m("Leavers", "Leavers"),
        m("Annualised Turnover %", "Turnover, annualised"),
        m("Early Leaver Share %", "Leavers in year one"),
    ]))

    v.append(chart(
        "vHeadcount", "lineChart", 24, 284, 900, 300, 600,
        column("Date", "Month Start", "Month"), [m("Headcount")],
        "Headcount at each month-end",
        "Builds for four years, peaks at the end of 2022, and falls through 2023 as leavers "
        "outrun joiners",
        sort=sort_by(column("Date", "Month Start"), "Ascending"),
        colours=series_colour({"Metrics.Headcount": NAVY}),
    ))

    v.append(table_visual(
        "vYears", 940, 284, 476, 300, 610,
        [
            column("Date", "Year"),
            m("Joiners", "Joiners"),
            m("Leavers", "Leavers"),
            m("Net Change", "Net"),
            m("Average Headcount", "Avg headcount"),
            m("Annualised Turnover %", "Turnover"),
        ],
        sort_by(column("Date", "Year"), "Ascending"),
        "Year by year",
        "2018 holds five months and 2023 seven; turnover is annualised over the months present",
    ))

    v.append(chart(
        "vFlows", "clusteredColumnChart", 24, 600, 452, 276, 620,
        column("Date", "Year"), [m("Joiners"), m("Leavers")],
        "Joiners and leavers by year",
        "Leavers rise every year; in 2023 they overtake joiners",
        sort=sort_by(column("Date", "Year"), "Ascending"),
        colours=series_colour({"Metrics.Joiners": NAVY, "Metrics.Leavers": GOLD}),
        show_legend=True,
    ))

    v.append(table_visual(
        "vDepts", 492, 600, 924, 276, 630,
        [
            column("Employee", "Department"),
            m("Headcount", "Headcount"),
            m("Joiners", "Joiners"),
            m("Leavers", "Leavers"),
            m("Annualised Turnover %", "Turnover"),
            m("Early Leaver Share %", "Year-one leavers"),
            m("Engagement Score", "Engagement"),
        ],
        sort_by(m("Headcount")),
        "By department",
        "Production is two thirds of the workforce, so it sets every company-wide rate",
    ))

    return page("pgOverview", "Overview"), v


def page_attrition() -> tuple[dict, list[dict]]:
    v: list[dict] = []
    v += masthead(
        "Att",
        "Who leaves, and when",
        "Nearly half of everyone who leaves goes inside their first year, so attrition here is "
        "a hiring and onboarding question before it is a retention one. Leavers are counted "
        "on their exit date, including the 991 people the HR system still lists as Active.",
        "02 / ATTRITION",
    )
    v += year_controls("Att")

    v.append(kpi_card("vKpiAtt", 24, 176, 1392, 92, 500, [
        m("Leavers", "Leavers"),
        m("Turnover 12M %", "Turnover, last 12 months"),
        m("Early Leaver Share %", "Left in year one"),
        m("Median Tenure at Exit", "Median years at exit"),
        m("Voluntary Share %", "Voluntary"),
    ]))

    v.append(chart(
        "vRolling", "lineChart", 24, 284, 900, 300, 600,
        column("Date", "Month Start", "Month"), [m("Turnover 12M %", "Turnover, rolling 12 months")],
        "Rolling twelve-month turnover",
        "Leavers in the twelve months to each month-end, over the average headcount across them",
        sort=sort_by(column("Date", "Month Start"), "Ascending"),
        colours=series_colour({"Metrics.Turnover 12M %": GOLD}),
    ))

    v.append(chart(
        "vTenure", "barChart", 940, 284, 476, 300, 610,
        column("Employee", "Tenure Band"), [m("Leavers")],
        "Leavers by length of service",
        "Under a year is the largest band by a distance",
        tooltips=[m("Median Tenure at Exit", "Median years")],
        sort=sort_by(column("Employee", "Tenure Band"), "Ascending"),
        colours=series_colour({"Metrics.Leavers": NAVY}), labels=data_labels(),
    ))

    v.append(chart(
        "vReasons", "columnChart", 24, 600, 452, 276, 620,
        column("Date", "Year"), [m("Leavers")],
        "Leavers by reason and year",
        "Voluntary merges the source's 'Voluntary' and 'Resignation'",
        series=column("Employee", "Leaver Group", active=False),
        sort=sort_by(column("Date", "Year"), "Ascending"),
        colours=value_colours("Employee", "Leaver Group", GROUP_COLOURS), show_legend=True,
    ))

    v.append(chart(
        "vDeptTurnover", "barChart", 492, 600, 452, 276, 630,
        column("Employee", "Department"), [m("Annualised Turnover %", "Turnover")],
        "Annualised turnover by department",
        tooltips=[m("Leavers"), m("Average Headcount", "Avg headcount")],
        sort=sort_by(m("Annualised Turnover %")),
        colours=series_colour({"Metrics.Annualised Turnover %": NAVY}), labels=data_labels(),
    ))

    v.append(note(
        "vReasonNote", 960, 600, 456, 276, 640,
        "Four reasons, in equal measure",
        ["The source's four termination types arrive in almost exactly equal numbers - 388, "
         "388, 380 and 377 - and a quarter of all exits are retirements, from a workforce whose "
         "median service at exit is about a year.",
         "That is the signature of generated data. The split is shown because it is in the "
         "file; nothing on this page is built on it.",
         "Tenure and timing are the parts of this dataset that behave like a real workforce, "
         "and they are what the page leads with."],
    ))

    return page("pgAttrition", "Attrition"), v


def page_engagement() -> tuple[dict, list[dict]]:
    v: list[dict] = []
    v += masthead(
        "Eng",
        "Engagement and learning",
        "One survey response and one training record per person, August 2022 to August 2023. "
        "Over four in ten are dated when the person did not work here. Headline figures count "
        "in-employment records only; the rest are shown beside them, not quietly dropped.",
        "03 / ENGAGEMENT & LEARNING",
    )
    v += year_controls("Eng")

    v.append(kpi_card("vKpiEng", 24, 176, 1392, 92, 500, [
        m("Engagement Score", "Engagement, 1-5"),
        m("Satisfaction Score", "Satisfaction, 1-5"),
        m("Work-Life Balance Score", "Work-life balance, 1-5"),
        m("Completion Rate %", "Training completed or passed"),
        m("Training Cost", "Training cost, in employment"),
    ]))

    v.append(chart(
        "vEngDept", "clusteredBarChart", 24, 284, 452, 300, 600,
        column("Employee", "Department"),
        [m("Engagement Score", "In employment"),
         m("Engagement Score (all responses)", "All responses")],
        "Engagement by department",
        "The two means barely differ - the problem is that the rows exist at all",
        sort=sort_by(m("Engagement Score")),
        colours=series_colour({"Metrics.Engagement Score": NAVY,
                               "Metrics.Engagement Score (all responses)": LIGHT}),
        show_legend=True,
    ))

    v.append(table_visual(
        "vPrograms", 492, 284, 924, 300, 610,
        [
            column("Program", "Program"),
            m("Training Records", "Records"),
            m("Completion Rate %", "Completed"),
            m("Training Days", "Days"),
            m("Training Cost", "Cost"),
            m("Cost per Record", "Per record"),
            m("Training Cost Outside Employment", "Cost, not employed"),
        ],
        sort_by(m("Training Cost")),
        "Training by programme",
        "The last column is spend booked against people who had not started or had already left",
    ))

    v.append(chart(
        "vCostSplit", "clusteredColumnChart", 24, 600, 700, 276, 620,
        column("Program", "Program"),
        [m("Training Cost", "In employment"),
         m("Training Cost Outside Employment", "Not employed at the time")],
        "Training cost by programme, and who it was spent on",
        sort=sort_by(m("Training Cost")),
        colours=series_colour({"Metrics.Training Cost": NAVY,
                               "Metrics.Training Cost Outside Employment": GOLD}),
        show_legend=True,
    ))

    v.append(note(
        "vCostNote", 740, 600, 676, 276, 630,
        "$735,145 of training nobody can place",
        ["1,317 of the 3,000 training records are dated outside the person's employment - 288 "
         "before they started and 1,029 after they left. They carry 44% of the recorded cost.",
         "The engagement survey has the same shape: 1,338 responses from people who did not "
         "work here on the survey date.",
         "In a real HR estate this is a join problem - training and survey systems keyed on an "
         "ID that was reused, or never closed when someone left. Either way the fix belongs "
         "upstream; the report's job is to count it rather than average it in."],
    ))

    return page("pgEngagement", "Engagement & learning"), v


def page_quality() -> tuple[dict, list[dict]]:
    v: list[dict] = []
    v += masthead(
        "Dq",
        "What the source gets wrong",
        "Every figure in this report rests on four decisions about the data. This page shows "
        "the evidence for each, so a reviewer can disagree with a decision rather than having "
        "to find it.",
        "04 / DATA QUALITY",
    )

    v.append(kpi_card("vKpiDq", 24, 176, 1392, 92, 500, [
        m("Employees", "Employee records"),
        m("Status Conflicts", "Status contradicts dates"),
        m("Status Conflict Rate %", "Share of records"),
        m("Surveys Outside Employment", "Surveys, not employed"),
        m("Training Records Outside Employment", "Training, not employed"),
    ]))

    v.append(table_visual(
        "vStatusMatrix", 24, 284, 700, 300, 600,
        [column("Employee", "Source Status", "HR system says"), m("Employees", "People")],
        None,
        "HR-system status against the dates",
        "Rows are what the system says; columns are what the start and exit dates say",
        totals=True,
        columns=[column("Employee", "Status", "Dates say")],
    ))

    v.append(note(
        "vStatusNote", 740, 284, 676, 300, 610,
        "Status is taken from the dates",
        ["991 people are 'Active' with an exit date that has already passed. All 69 'Future "
         "Start' employees started years ago, and every one of them has since left. All 86 on "
         "'Leave of Absence' have an exit date too.",
         "A status field is a label someone has to remember to update; an exit date is an "
         "event. Where they disagree the report believes the event, and keeps the label beside "
         "it as 'Source Status' so the disagreement stays visible.",
         "Counted the other way - Active, on leave or starting - headcount at August 2023 "
         "would read 2,613 against 1,480 from the dates: 77% too high."],
    ))

    v.append(note(
        "vRecruitNote", 24, 600, 452, 276, 620,
        "Recruitment is not this company's",
        ["The applicant file's IDs run 1001 to 4000, exactly like employee IDs, so it joins "
         "perfectly - to the wrong people. On a shared ID, 0 of 3,000 names match.",
         "None of the 3,000 applicants applied for a job title that exists in the company, and "
         "every one pairs a US state with a country that is not the US.",
         "It is tested in the build and left out of the model. A funnel built on it would be a "
         "funnel of someone else's vacancies."],
    ))

    v.append(note(
        "vEventsNote", 492, 600, 452, 276, 630,
        "Events outside employment",
        ["Surveys and training are linked to employees by ID, and the link holds for all "
         "3,000. The dates do not: 1,338 surveys and 1,317 training records fall before the "
         "person started or after they left.",
         "Each carries an 'In Employment' flag. Headline measures use in-employment records; "
         "the naive figure sits beside them on page 3."],
    ))

    v.append(note(
        "vSmallNote", 960, 600, 456, 276, 640,
        "Smaller fixes, all in the ETL",
        ["Department has a trailing space on all 2,020 Production rows - trimmed, or Production "
         "becomes two departments the day a clean source joins it.",
         "Two date formats: dd-Mon-yy for most fields, dd-mm-yyyy for birth and survey dates - "
         "proven day-first because the first number exceeds 12 in 1,823 rows and the second "
         "never does.",
         "Names, emails, supervisor names and dates of birth are dropped before the model sees "
         "them. Age survives only as a band."],
    ))

    return page("pgQuality", "Data quality"), v


# --------------------------------------------------------------------------------------------
# Theme and writers
# --------------------------------------------------------------------------------------------


def theme() -> dict:
    return {
        # Desktop caches themes by name, and the name must match the filename exactly.
        "name": THEME_NAME,
        "dataColors": [NAVY, GOLD, SLATE, LIGHT, GOOD, BAD, GOLD_TEXT, MUTED],
        "background": PAPER,
        "foreground": BODY,
        "tableAccent": INK,
        "good": GOOD,
        "neutral": MUTED,
        "bad": BAD,
        "textClasses": {
            "title": {"fontFace": "Segoe UI Semibold", "fontSize": 14, "color": INK},
            "header": {"fontFace": "Segoe UI Semibold", "fontSize": 11, "color": INK},
            "label": {"fontFace": "Segoe UI", "fontSize": 9, "color": BODY},
            "callout": {"fontFace": "Segoe UI", "fontSize": 20, "color": INK},
        },
        "visualStyles": {
            "*": {
                "*": {
                    "background": [{"show": True, "color": {"solid": {"color": CARD}}}],
                    "border": [{"show": True, "color": {"solid": {"color": RULE}}, "radius": 4}],
                    "padding": [{"top": 8, "bottom": 8, "left": 10, "right": 10}],
                    "dropShadow": [{"show": False}],
                }
            }
        },
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # No BOM: a BOM breaks .platform and PBIR parsing. newline="\n" because write_text otherwise
    # uses the platform ending, and the repo is normalised to LF.
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")


def rmtree_retry(path: Path) -> None:
    """OneDrive intermittently holds a directory handle open; the files are gone by then."""
    for attempt in range(4):
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except PermissionError:
            if attempt == 3:
                shutil.rmtree(path, ignore_errors=True)
                return
            time.sleep(0.4)


def main() -> None:
    if PAGES.exists():
        rmtree_retry(PAGES)

    bookmarks_dir = REPORT / "definition" / "bookmarks"
    if bookmarks_dir.exists():
        rmtree_retry(bookmarks_dir)

    # Page 05 is built on the milestone_pbir library and brings its filter-panel bookmarks.
    bookmarks: list[dict] = []

    def page_year_on_year() -> tuple[dict, list[dict]]:
        pg, visuals, marks = yoy_page.build()
        bookmarks.extend(marks)
        return pg, visuals

    builders = [page_overview, page_attrition, page_engagement, page_quality, page_year_on_year]
    order: list[str] = []
    total_visuals = 0

    for build in builders:
        pg, visuals = build()
        page_dir = PAGES / pg["name"]
        write_json(page_dir / "page.json", pg)
        names = set()
        for node in visuals:
            if node["name"] in names:
                print(f"ERROR: duplicate visual name {node['name']} on {pg['name']}",
                      file=sys.stderr)
                sys.exit(1)
            names.add(node["name"])
            write_json(page_dir / "visuals" / node["name"] / "visual.json", node)
        order.append(pg["name"])
        total_visuals += len(visuals)
        print(f"  {pg['name']:14s} {len(visuals):2d} visuals  ({pg['displayName']})")

    stale = [d for d in PAGES.rglob("visuals/*")
             if d.is_dir() and not (d / "visual.json").exists()]
    for d in stale:
        rmtree_retry(d)
        if d.exists():
            print(f"ERROR: could not remove stale visual directory {d}. "
                  f"Close Power BI Desktop and run again.", file=sys.stderr)
            sys.exit(1)
        print(f"  swept stale visual directory {d.name}")

    write_json(PAGES / "pages.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": order,
        "activePageName": order[0],
    })

    for mark in bookmarks:
        write_json(bookmarks_dir / f"{mark['name']}.bookmark.json", mark)
    write_json(bookmarks_dir / "bookmarks.json", milestone_pbir.bookmarks_metadata(bookmarks))

    write_json(REPORT / "definition" / "version.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0",
    })

    write_json(REPORT / "definition" / "report.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {
            "baseTheme": {
                "name": "CY25SU12",
                "reportVersionAtImport": {"visual": "2.12.0", "report": "3.4.0",
                                          "page": "2.3.1"},
                "type": "SharedResources",
            },
            "customTheme": {
                "name": THEME_NAME,
                "reportVersionAtImport": {"visual": "2.12.0", "report": "3.4.0",
                                          "page": "2.3.1"},
                "type": "RegisteredResources",
            },
        },
        "objects": {
            "section": [{"properties": {"verticalAlignment": lit("Top")}}],
            "outspacePane": [{"properties": {"expanded": lit(False)}}],
        },
        "resourcePackages": [
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": THEME_NAME, "path": THEME_NAME, "type": "CustomTheme"},
                       {"name": MARK_NAME, "path": MARK_NAME, "type": "Image"}]},
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "CY25SU12", "path": "BaseThemes/CY25SU12.json",
                        "type": "BaseTheme"}]},
        ],
        "settings": {"useStylableVisualContainerHeader": True, "useEnhancedTooltips": False},
    })

    RESOURCES.mkdir(parents=True, exist_ok=True)
    write_json(RESOURCES / THEME_NAME, theme())
    shutil.copyfile(ASSETS / "milestone-mark.svg", RESOURCES / MARK_NAME)

    write_json(REPORT / "definition.pbir", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}},
    })

    write_json(REPORT / ".platform", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": NAME},
        "config": {"version": "2.0", "logicalId": "5e2a9c47-8d13-4f6b-b0e5-3a7c1d9f2e68"},
    })

    write_json(ROOT / f"{NAME}.pbip", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })

    print(f"\n{len(order)} pages, {total_visuals} visuals written")


if __name__ == "__main__":
    main()
