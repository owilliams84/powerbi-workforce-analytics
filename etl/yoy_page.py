"""Page 05, Year on Year - the report half. Called from build_report.py.

Built from design/yoy-mockup.html. Every helper comes from etl/milestone_pbir.py (the
milestone-report-design library); this file is layout only. Measures come from the
'YoY Metrics' table written by etl/yoy_model.py.
"""

from __future__ import annotations

from milestone_pbir import (
    BODY, MUTED, NAVY, SLATE, Fields, action_button, axis, button_slicer,
    categorical_filter, colour, column, dynamic_chrome, dynamic_text, filter_panel, lit, masthead,
    obj, page, pivot_objects, sort_by, svg_image, visual,
)

PAGE_NAME = "pgYearOnYear"
F = Fields("YoY Metrics")
MONTH = column("Date", "Month Short", "Month")


def build() -> tuple[dict, list[dict], list[dict]]:
    v: list[dict] = masthead("Yoy", "Year on year", "05 / YEAR ON YEAR") + [
        dynamic_text("vStandYoy", 18, 112, 700, 56, 95, F.expr("YoY Standfirst")),

        button_slicer("vYearYoy", 740, 72, 270, 64, 400, "Date", "Year", 2023, 5, header="YEAR",
                      filters=[categorical_filter("fYearYoy", "Date", "Year", [2019, 2020, 2021, 2022, 2023])]),
        button_slicer("vCompYoy", 1022, 72, 228, 64, 410, "YoY Comparison", "Comparison", "Prior year", 2,
                      header="COMPARE THE SAME MONTHS WITH"),
        action_button("vFiltersYoy", 1262, 96, 154, 34, 420, "Filters", "bmYoyFiltersOpen"),
        dynamic_text("vChipYoy", 1250, 132, 178, 28, 430, F.expr("YoY Filter Summary"),
                     size=8.0, color=MUTED, align="center"),
    ]
    for i, card in enumerate(["YoY Card Headcount", "YoY Card Leavers", "YoY Card Turnover", "YoY Card Divisions"]):
        v.append(svg_image(f"vCard{i + 1}Yoy", 24 + i * 352, 176, 336, 140, 500 + i * 10, F.expr(card)))

    v.append(visual(
        "vLineYoy", "lineChart", 24, 332, 688, 264, 600,
        query={"queryState": {
            "Category": {"projections": [MONTH]},
            "Y": {"projections": [F.m("YoY Chart This", "This year"), F.m("YoY Chart Comparison", "Comparison")]}},
            "sortDefinition": sort_by(MONTH, "Ascending")},
        objects={
            "categoryAxis": axis(), "valueAxis": axis(gridlines=True),
            "legend": [{"properties": {"show": lit(True), "position": lit("Top"), "showTitle": lit(False),
                                       "fontSize": lit(8.5), "labelColor": colour(MUTED)}}],
            "labels": obj(show=lit(False)),
            "dataPoint": [{"properties": {"fill": colour(NAVY)}, "selector": {"metadata": F.ref("YoY Chart This")}},
                          {"properties": {"fill": colour(SLATE)}, "selector": {"metadata": F.ref("YoY Chart Comparison")}}],
            "lineStyles": [
                {"properties": {"strokeWidth": lit(2), "showMarker": lit(False), "lineStyle": lit("solid")}},
                {"properties": {"lineStyle": lit("dashed"), "strokeWidth": lit(2)},
                 "selector": {"metadata": F.ref("YoY Chart Comparison")}},
            ],
        },
        container=dynamic_chrome(F.expr("YoY Title Line Chart"), F.expr("YoY Subtitle Line Chart")),
    ))
    # 100px a tile: at 87px "Headcount" clipped to "Headcou...".
    v.append(button_slicer("vMetricYoy", 402, 338, 300, 40, 610, "YoY Chart Metric", "Metric", "Leavers", 3))

    v.append(visual(
        "vVarYoy", "columnChart", 728, 332, 688, 264, 620,
        query={"queryState": {
            "Category": {"projections": [MONTH]},
            "Y": {"projections": [F.m("YoY Chart Change", "Change")]},
            "Tooltips": {"projections": [F.m("YoY Chart This", "This year"), F.m("YoY Chart Comparison", "Comparison")]}},
            "sortDefinition": sort_by(MONTH, "Ascending")},
        objects={
            "categoryAxis": axis(), "valueAxis": axis(gridlines=True),
            "legend": obj(show=lit(False)),
            "labels": [{"properties": {"show": lit(True), "fontSize": lit(8.0), "color": colour(BODY)}}],
            "dataPoint": [{"properties": {"fill": {"solid": {"color": F.expr("YoY Chart Change Colour")}}},
                           "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}],
        },
        container=dynamic_chrome(F.expr("YoY Title Variance Chart"), F.expr("YoY Subtitle Variance Chart")),
    ))

    dept_objects = pivot_objects()
    dept_objects["values"] = F.values_with_colour("Dept Turnover Colour", "YoY Turnover Change pp")
    v.append(visual(
        "vDeptYoy", "pivotTable", 24, 612, 688, 264, 700,
        query={"queryState": {
            "Rows": {"projections": [column("Employee", "Department")]},
            "Values": {"projections": [F.m("Dept Headcount", "Headcount"), F.m("Dept Leavers", "Leavers"),
                                       F.m("Dept Leavers Comparison", "was"), F.m("Dept Turnover", "Turnover"),
                                       F.m("YoY Turnover Comparison", "was "), F.m("YoY Turnover Change pp", "Change, pp"),
                                       F.m("Dept Turnover Bar", " ")]}},
            "sortDefinition": sort_by(F.m("YoY Turnover Change pp"), "Descending")},
        objects=dept_objects,
        container=dynamic_chrome(F.expr("YoY Title Department Table"), F.expr("YoY Subtitle Department Table")),
    ))

    div_objects = pivot_objects()
    div_objects["values"] = F.values_with_colour("Division Change Colour", "YoY Leaver Change")
    v.append(visual(
        "vDivYoy", "pivotTable", 728, 612, 688, 264, 710,
        query={"queryState": {
            "Rows": {"projections": [column("Employee", "Division")]},
            "Values": {"projections": [F.m("Division Rank", "Rank"), F.m("Division Leavers", "Leavers"),
                                       F.m("Division Leavers Comparison", "was"), F.m("YoY Leaver Change", "Change"),
                                       F.m("Division Leaver Bar", " ")]}},
            "sortDefinition": sort_by(F.m("Division Rank"), "Ascending")},
        objects=div_objects,
        container=dynamic_chrome(F.expr("YoY Title Division Table"), F.expr("YoY Subtitle Division Table")),
        filters=[F.range_filter("fDivYoyTop", "Division Rank", 1, 8)],
    ))
    v.append(button_slicer("vDivShowYoy", 1258, 618, 148, 40, 720, "Division Ranking", "Show", "Top", 2))

    panel, bookmarks = filter_panel("Yoy", "bmYoyFilters", "Year on year filters", PAGE_NAME, [
        ("vUnitYoy", "Employee", "Business Unit", "BUSINESS UNIT"),
        ("vTypeYoy", "Employee", "Employee Type", "EMPLOYEE TYPE"),
    ])
    v += panel

    return page(PAGE_NAME, "Year on year"), v, bookmarks
