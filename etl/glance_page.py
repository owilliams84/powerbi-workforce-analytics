"""The landing page, At a glance - the report half. Called from build_report.py.

Built from design/glance-mockup.html on the milestone_pbir library; this file is layout only.
Measures come from 'Glance Metrics' (etl/glance_model.py), 'YoY Metrics' and 'Metrics'.

The page has a rail down the left: six page-navigation buttons, each a white outline icon (a
registered SVG from etl/glance_icons.py) under a transparent button that carries the label and
the link. The brand band still runs the full width above it, which crop_screenshots.py needs.
"""

from __future__ import annotations

from glance_icons import svg_file
from milestone_pbir import (
    BODY, CARD, GOLD, INK, LIGHT, NAVY, SLATE, Fields, axis, button_slicer, categorical_filter,
    colour, column, dropdown, dynamic_chrome, dynamic_text, lit, mark, masthead, no_chrome, obj, page,
    pivot_objects, sort_by, svg_image, textbox, visual,
)

PAGE_NAME = "pgGlance"
# Display units "None". lit(1.0) writes 1.0D, which the enum rejects; auto units turn 207 into 0.2K.
WHOLE_NUMBERS = {"expr": {"Literal": {"Value": "1D"}}}
G = Fields("Glance Metrics")
Y = Fields("YoY Metrics")
B = Fields("Metrics")

RAIL_W = 176
LEFT = RAIL_W + 16                       # content starts here and runs to 1416
COLS = [(LEFT, 476), (680, 340), (1032, 384)]
ROWS = [272, 472, 672]
# The bottom row is the tall one: a bar chart will not draw a bar under about 26px, and six
# departments scrolled at 196.
PANEL_H = {272: 188, 472: 188, 672: 212}

# (icon, label, page) in rail order. The page names are the ones build_report.py gives them.
RAIL = [("nav-glance", "At a glance", PAGE_NAME), ("nav-overview", "Overview", "pgOverview"),
        ("nav-attrition", "Attrition", "pgAttrition"), ("nav-engagement", "Engagement", "pgEngagement"),
        ("nav-quality", "Data quality", "pgQuality"), ("nav-yoy", "Year on year", "pgYearOnYear")]


# The current page's row: a navy tile with a gold edge. One image, because a 3px textbox cannot be
# drawn - its padding makes it 20px wide.
ACTIVE_NAME = "GlanceNavActive.svg"
ACTIVE_SVG = (f"<svg viewBox='0 0 {RAIL_W - 20} 44' xmlns='http://www.w3.org/2000/svg'>"
              f"<rect width='{RAIL_W - 20}' height='44' rx='4' fill='{NAVY}'/><rect width='3' height='44' fill='{GOLD}'/></svg>\n")


def resource_name(icon: str) -> str:
    return "Glance" + "".join(part.capitalize() for part in icon.split("-")) + ".svg"


def resources() -> dict[str, str]:
    """Registered image name -> SVG text, for build_report.py to write and list in report.json."""
    return {ACTIVE_NAME: ACTIVE_SVG, **{resource_name(icon): svg_file(icon, "#FFFFFF", GOLD) for icon, _, _ in RAIL}}


def nav_button(name: str, x: int, y: int, w: int, h: int, z: int, label: str, target: str, current: bool) -> dict:
    """A transparent button over its icon: left-aligned label, page-navigation link."""
    def dual(props):
        return [{"properties": props}, {"properties": props, "selector": {"id": "default"}}]
    container = no_chrome()
    container["visualLink"] = obj(show=lit(True), type=lit("PageNavigation"), navigationSection=lit(target))
    node = visual(name, "actionButton", x, y, w, h, z, container=container)
    node["visual"]["objects"] = {
        "shape": [{"properties": {"tileShape": lit("rectangleRoundedByPixel"), "rectangleRoundedCurve": lit(4)}}],
        "fill": dual({"show": lit(True), "fillColor": colour(NAVY), "transparency": lit(100.0)})
        + [{"properties": {"show": lit(True), "fillColor": colour(NAVY), "transparency": lit(40.0)},
            "selector": {"id": "hover"}}],
        "outline": dual({"show": lit(False)}),
        "icon": dual({"show": lit(False)}),
        "text": dual({"show": lit(True), "text": lit(label), "fontColor": colour(CARD), "fontSize": lit(10.0),
                      "bold": lit(current), "horizontalAlignment": lit("left"), "leftMargin": lit(44)}),
    }
    node["howCreated"] = "InsertVisualButton"
    return node


def rail() -> list[dict]:
    out = [textbox("vRailGlance", 0, 60, RAIL_W, 840, 55, [[{"text": "", "size": 6, "color": INK}]], background=INK)]
    for i, (icon, label, target) in enumerate(RAIL):
        y = 76 + i * 50
        if target == PAGE_NAME:
            out.append(mark("vRailOnGlance", 10, y, RAIL_W - 20, 44, 56, ACTIVE_NAME))
        out.append(mark(f"vNavIcon{i}Glance", 24, y + 12, 20, 20, 58, resource_name(icon)))
        out.append(nav_button(f"vNav{i}Glance", 10, y, RAIL_W - 20, 44, 59, label, target, target == PAGE_NAME))
    return out


def chrome(title: str, subtitle) -> dict:
    return dynamic_chrome(G.expr(title), subtitle if isinstance(subtitle, dict) else lit(subtitle))


def slice_colours(table: str, col: str, palette: dict[str, str]) -> list[dict]:
    """donut dataPoint fills, one per category value."""
    ref = {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": col}}
    return [{"properties": {"fill": colour(hex_code)},
             "selector": {"data": [{"scopeId": {"Comparison": {
                 "ComparisonKind": 0, "Left": ref, "Right": lit(value)["expr"]}}}]}}
            for value, hex_code in palette.items()]


def donut(name: str, slot: tuple, z: int, col: str, title: str, subtitle: str, palette: dict[str, str]) -> dict:
    (x, w), y = slot
    field = column("Employee", col)
    return visual(
        name, "donutChart", x, y, w, PANEL_H[y], z,
        query={"queryState": {"Category": {"projections": [field]},
                              "Y": {"projections": [B.m("Headcount", "Headcount")]}},
               "sortDefinition": sort_by(B.m("Headcount"), "Descending")},
        objects={
            "legend": [{"properties": {"show": lit(True), "position": lit("Right"), "showTitle": lit(False),
                                       "fontSize": lit(8.0), "labelColor": colour(BODY)}}],
            "labels": [{"properties": {"show": lit(True), "labelStyle": lit("Data value, percent of total"),
                                       "fontSize": lit(8.5), "color": colour(BODY), "percentageLabelPrecision": lit(1),
                                       "labelDisplayUnits": WHOLE_NUMBERS}}],
            "slices": [{"properties": {"innerRadiusRatio": lit(62)}}],
            "dataPoint": slice_colours("Employee", col, palette),
        },
        container=chrome(title, subtitle),
    )


def bars(name: str, vtype: str, slot: tuple, z: int, category: dict, value: dict, fill: str, title: str, subtitle,
         filters: list | None = None, label_size: float = 8.5, label_room: int | None = None) -> dict:
    """A column or bar chart of one measure. label_room is the share of the width (percent) a bar
    chart may give its category labels; the default 25 cut 'Production Technician I' and 'II'
    down to the same 'Production Te...'."""
    (x, w), y = slot
    category_axis = {"fontSize": lit(label_size)}
    if label_room:
        category_axis["maxMarginFactor"] = lit(label_room)
    return visual(
        name, vtype, x, y, w, PANEL_H[y], z,
        query={"queryState": {"Category": {"projections": [category]}, "Y": {"projections": [value]}},
               "sortDefinition": sort_by(value, "Descending")},
        objects={
            "categoryAxis": axis(**category_axis),
            "valueAxis": [{"properties": {"show": lit(False), "showAxisTitle": lit(False), "gridlineShow": lit(False)}}],
            "legend": obj(show=lit(False)),
            "labels": [{"properties": {"show": lit(True), "fontSize": lit(8.0), "color": colour(BODY),
                                       "labelDisplayUnits": WHOLE_NUMBERS}}],
            "dataPoint": [{"properties": {"fill": colour(fill)}}],
        },
        container=chrome(title, subtitle), filters=filters,
    )


def top_n(name: str, table: str, col: str, entity: str, by: str, n: int) -> dict:
    """Visual-level Top N of `table`[`col`] by a measure."""
    target = {"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": col}}
    return {
        "name": name, "type": "TopN",
        "field": {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": col}},
        "filter": {"Version": 2, "From": [
            {"Name": "subquery", "Type": 2, "Expression": {"Subquery": {"Query": {
                "Version": 2,
                "From": [{"Name": "t", "Entity": table, "Type": 0}, {"Name": "m", "Entity": entity, "Type": 0}],
                "Select": [{**target, "Name": "field"}],
                "OrderBy": [{"Direction": 2, "Expression": {"Measure": {
                    "Expression": {"SourceRef": {"Source": "m"}}, "Property": by}}}],
                "Top": n}}}},
            {"Name": "t", "Entity": table, "Type": 0}],
            "Where": [{"Condition": {"In": {"Expressions": [target], "Table": {"SourceRef": {"Source": "subquery"}}}}}]},
    }


def build() -> tuple[dict, list[dict], list[dict]]:
    v: list[dict] = masthead("Glance", "Workforce at a glance", "00 / AT A GLANCE", title_width=460)
    for node in v:                       # the title sits right of the rail; the band and mark do not move
        if node["name"] == "vTitleGlance":
            node["position"]["x"] = LEFT
            node["position"]["y"] = 66
    v += rail()
    v += [
        dynamic_text("vStandGlance", LEFT - 6, 104, 470, 48, 95, G.expr("Glance Standfirst"), size=9.5),
        button_slicer("vYearGlance", 666, 72, 270, 64, 400, "Date", "Year", 2023, 5, header="YEAR",
                      filters=[categorical_filter("fYearGlance", "Date", "Year", [2019, 2020, 2021, 2022, 2023])]),
        dropdown("vDeptGlance", 946, 66, 150, 80, 410, "Employee", "Department", "DEPARTMENT"),
        dropdown("vUnitGlance", 1106, 66, 150, 80, 420, "Employee", "Business Unit", "BUSINESS UNIT"),
        dropdown("vRoleGlance", 1266, 66, 150, 80, 430, "Employee", "Title", "JOB ROLE"),
    ]
    for i, tile in enumerate(["Headcount", "Hires", "Turnover", "Engagement", "Rating"]):
        v.append(svg_image(f"vTile{i + 1}Glance", LEFT + i * 247, 156, 235, 104, 500 + i * 10, G.expr(f"Glance Tile {tile}")))

    department = column("Employee", "Department")
    month = column("Date", "Month Short", "Month")

    v.append(bars("vDeptGlance2", "columnChart", (COLS[0], ROWS[0]), 600, department, B.m("Headcount", "Headcount"), NAVY,
                  "Glance Title Department", "People employed at the year's last month-end, by department"))
    v.append(donut("vGenderGlance", (COLS[1], ROWS[0]), 610, "Gender", "Glance Title Gender", "Headcount by gender",
                   {"Female": NAVY, "Male": GOLD}))
    v.append(bars("vUnitGlance2", "columnChart", (COLS[2], ROWS[0]), 620, column("Employee", "Business Unit"),
                  B.m("Headcount", "Headcount"), SLATE, "Glance Title Unit", "Headcount by business unit", label_size=8.0))

    (x, w) = COLS[0]
    v.append(visual(
        "vLineGlance", "lineChart", x, ROWS[1], w, PANEL_H[ROWS[1]], 630,
        query={"queryState": {
            "Category": {"projections": [month]},
            "Y": {"projections": [Y.m("YoY Headcount", "This year"), Y.m("YoY Headcount Comparison", "Year before")]}},
            "sortDefinition": sort_by(month, "Ascending")},
        objects={
            "categoryAxis": axis(), "valueAxis": axis(gridlines=True),
            "legend": obj(show=lit(False)),
            "labels": obj(show=lit(False)),
            "dataPoint": [{"properties": {"fill": colour(NAVY)}, "selector": {"metadata": Y.ref("YoY Headcount")}},
                          {"properties": {"fill": colour(SLATE)}, "selector": {"metadata": Y.ref("YoY Headcount Comparison")}}],
            "lineStyles": [
                {"properties": {"strokeWidth": lit(2), "showMarker": lit(False), "lineStyle": lit("solid")}},
                {"properties": {"lineStyle": lit("dashed"), "strokeWidth": lit(2)},
                 "selector": {"metadata": Y.ref("YoY Headcount Comparison")}},
            ],
        },
        container=dynamic_chrome(G.expr("Glance Title Line"), G.expr("Glance Subtitle Line")),
    ))
    v.append(donut("vTypeGlance", (COLS[1], ROWS[1]), 640, "Employee Type", "Glance Title Type", "Headcount by employee type",
                   {"Full-Time": NAVY, "Contract": GOLD, "Part-Time": LIGHT}))
    v.append(bars("vRolesGlance", "barChart", (COLS[2], ROWS[1]), 650, column("Employee", "Title", "Job role"),
                  B.m("Headcount", "Headcount"), NAVY, "Glance Title Roles", "Top five job roles by headcount", label_room=50,
                  filters=[top_n("fRolesGlance", "Employee", "Title", "Metrics", "Headcount", 5)]))

    (x, w) = COLS[0]
    hires = pivot_objects(image_width=None)
    hires["values"] = [{"properties": {"fontSize": lit(9.0), "fontColorPrimary": colour(BODY),
                                       "backColorPrimary": colour(CARD), "backColorSecondary": colour(CARD)}}]
    hires["columnHeaders"][0]["properties"]["alignment"] = lit("Left")
    v.append(visual(
        "vHiresGlance", "pivotTable", x, ROWS[2], w, PANEL_H[ROWS[2]], 660,
        query={"queryState": {
            "Rows": {"projections": [column("Employee", "Employee")]},
            "Values": {"projections": [G.m("Glance Hire Department", "Department"), G.m("Glance Hire Role", "Job role"),
                                       G.m("Glance Hire Joined", "Joined")]}},
            "sortDefinition": sort_by(G.m("Glance Hire Joined"), "Descending")},
        objects=hires,
        container=dynamic_chrome(lit("Most recent hires"), G.expr("Glance Title Hires")),
        filters=[top_n("fHiresGlance", "Employee", "Employee", "Glance Metrics", "Glance Hire Order", 5)],
    ))
    v.append(bars("vTurnGlance", "barChart", (COLS[1], ROWS[2]), 670, department, Y.m("YoY Turnover", "Turnover"), GOLD,
                  "Glance Title Turnover", G.expr("Glance Subtitle Turnover"), label_room=45))
    v.append(donut("vPerfGlance", (COLS[2], ROWS[2]), 680, "Performance", "Glance Title Performance",
                   "Headcount by performance rating",
                   {"Fully Meets": NAVY, "Exceeds": GOLD, "Needs Improvement": SLATE, "PIP": LIGHT}))

    return page(PAGE_NAME, "At a glance"), v, []

