"""Diff the landing page's figures in the live model against etl/glance_expected.py (pandas).

    python etl/verify_glance.py          # with the PBIP open in Power BI Desktop

For each state - a year, optionally with one of the page's dropdowns pinned - one DAX query asks
the model for every figure the page shows: the five tiles, every split, both headcount lines,
turnover by department and the five most recent hires in order. TREATAS pins the slicers the way
the page does. The query goes through etl/query_model.ps1 from a temp file, so nothing in the
project folder changes while Desktop has it open. Exit code 1 on any mismatch.
"""

from __future__ import annotations

import csv
import io
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

from glance_expected import expected

ETL = Path(__file__).resolve().parent
STATES = [(2023, {}), (2022, {}), (2020, {}), (2019, {}), (2023, {"Department": "Sales"}),
          (2021, {"Business Unit": "NEL"}), (2023, {"Title": "Production Technician I"})]
SPLITS = {"department": "Department", "gender": "Gender", "business_unit": "Business Unit",
          "employee_type": "Employee Type", "title": "Title", "performance": "Performance"}


def split(key: str, col: str, value: str) -> str:
    return (f'SELECTCOLUMNS(ADDCOLUMNS(VALUES(\'Employee\'[{col}]), "@v", {value}), '
            f'"k", "{key}|" & \'Employee\'[{col}], "v", [@v] + 0)')


def by_month(key: str, value: str) -> str:
    return (f'SELECTCOLUMNS(ADDCOLUMNS(VALUES(\'Date\'[Month No]), "@v", {value}), '
            f'"k", "{key}|" & \'Date\'[Month No], "v", [@v] + 0)')


def query(year: int, panel: dict[str, str]) -> str:
    scalars = {"headcount": "[YoY Headcount]", "headcount_was": "[YoY Headcount Comparison]",
               "joiners": "[YoY Joiners]", "joiners_was": "[YoY Joiners Comparison]",
               "turnover": "[YoY Turnover]", "turnover_was": "[YoY Turnover Comparison]",
               "engagement": "[Engagement Score]", "surveys": "[Surveys]", "rating": "[Glance Rating]"}
    blocks = [f'ROW("k", "{k}", "v", {v} + 0)' for k, v in scalars.items()]
    blocks += [split(k, col, "[Headcount]") for k, col in SPLITS.items()]
    blocks += [by_month("headcount_by_month", "[YoY Headcount]"),
               by_month("headcount_by_month_was", "[YoY Headcount Comparison]"),
               split("turnover_by_department", "Department", "[YoY Turnover]"),
               'SELECTCOLUMNS(TOPN(5, FILTER(ADDCOLUMNS(VALUES(\'Employee\'[Employee]), "@o", [Glance Hire Order]), '
               'NOT ISBLANK([@o])), [@o], DESC), "k", "hire|" & \'Employee\'[Employee], "v", [@o] + 0)']
    filters = [f"TREATAS({{{year}}}, 'Date'[Year])"]
    filters += [f'TREATAS({{"{v}"}}, \'Employee\'[{k}])' for k, v in panel.items()]
    return "EVALUATE\nCALCULATETABLE(\n    UNION(\n        " + ",\n        ".join(blocks) + "\n    ),\n    " + ",\n    ".join(filters) + "\n)\n"


def run(dax: str) -> dict[str, float]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "glance.dax"
        path.write_text(dax, encoding="utf-8")
        out = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                              str(ETL / "query_model.ps1"), "-DaxFile", str(path), "-Csv"],
                             check=True, capture_output=True, text=True).stdout
    rows = list(csv.reader(io.StringIO(out)))
    return {k: float(v or 0) for k, v in rows[1:]}


def flatten(e: dict) -> dict[str, float]:
    flat = {k: float(e[k] or 0) for k in ["headcount", "headcount_was", "joiners", "joiners_was", "turnover",
                                          "turnover_was", "engagement", "surveys", "rating"]}
    for key in [*SPLITS, "headcount_by_month", "headcount_by_month_was", "turnover_by_department"]:
        flat.update({f"{key}|{name}": float(v) for name, v in e[key].items()})
    for h in e["recent_hires"]:
        serial = (date.fromisoformat(h["joined"]) - date(1899, 12, 30)).days
        flat[f"hire|{h['employee']}"] = float(serial * 10000 + h["employee"])
    return flat


def main() -> None:
    total, bad = 0, []
    for year, panel in STATES:
        model, want = run(query(year, panel)), flatten(expected(year, panel))
        for key in sorted(set(model) | set(want)):
            total += 1
            if abs(model.get(key, 0.0) - want.get(key, 0.0)) > 1e-3:
                bad.append(f"{year} {panel or ''} {key}: model {model.get(key)}, pandas {want.get(key)}")
        print(f"  {year} {panel or 'no filter'}: {len(set(model) | set(want))} figures")
    print(f"{total} checks, {len(bad)} mismatches")
    for line in bad[:40]:
        print("  " + line)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
