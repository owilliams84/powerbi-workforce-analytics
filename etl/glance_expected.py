"""Expected figures for the landing page, At a glance, computed in pandas from the star schema.

The page reads one year. Stocks (headcount and every split of it) are taken at the year's last
month-end; flows (new hires, turnover) cover the months the year has a snapshot for, and compare
with the same months of the year before - the convention page 05 uses, from etl/yoy_expected.py.
Engagement and the recent-hires list follow the year slicer as it stands, part months included.

    python etl/glance_expected.py                     # 2023
    python etl/glance_expected.py 2022 "Department=Sales"
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from yoy_expected import months_of, period

DATA = Path(__file__).resolve().parents[1] / "data"
COLUMN_OF = {"Department": "Department", "Business Unit": "BusinessUnit", "Title": "Title"}
SPLITS = {"department": "Department", "gender": "Gender", "business_unit": "BusinessUnit",
          "employee_type": "EmployeeType", "title": "Title", "performance": "Performance"}


def expected(year: int, panel: dict[str, str]) -> dict:
    emp = pd.read_csv(DATA / "dim_employee.csv", parse_dates=["StartDate"])
    hc = pd.read_csv(DATA / "fact_headcount.csv", parse_dates=["Date"])
    mv = pd.read_csv(DATA / "fact_movement.csv", parse_dates=["Date"])
    en = pd.read_csv(DATA / "fact_engagement.csv", parse_dates=["Date"])
    # Snapshot months come from every employee: slicers narrow people, not the calendar.
    snapshots = {(d.year, d.month) for d in pd.to_datetime(hc.Date.unique())}
    for field, value in panel.items():
        emp = emp[emp[COLUMN_OF[field]] == value]
    hc, mv, en = (df.merge(emp, on="EmpID") for df in (hc, mv, en))
    for df in (hc, mv, en):
        df["Year"], df["Month"] = df.Date.dt.year, df.Date.dt.month

    months = months_of(snapshots, year)
    prior = months_of(snapshots, year - 1)
    comparable = bool(prior) and min(prior) <= min(months) and max(prior) >= max(months)
    now = period(hc, mv, year, months).loc["all"]
    was = period(hc, mv, year - 1, months).loc["all"] if comparable else None

    at_end = hc[(hc.Year == year) & (hc.Month == max(months))]
    surveys = en[(en.Year == year) & (en.InEmployment == "Yes")]
    hires = (mv[(mv.Year == year) & (mv.Movement == "Joiner")]
             .sort_values(["Date", "EmpID"], ascending=False).head(5))
    by_dept = period(hc, mv, year, months, "Department")

    return {
        "year": year, "months": [min(months), max(months)], "comparable": comparable,
        "headcount": int(now.headcount), "headcount_was": int(was.headcount) if comparable else None,
        "joiners": int(now.joiners), "joiners_was": int(was.joiners) if comparable else None,
        "turnover": round(now.turnover, 4), "turnover_was": round(was.turnover, 4) if comparable else None,
        "engagement": round(surveys.Engagement.mean(), 4) if len(surveys) else None,
        "surveys": len(surveys),
        "rating": round(at_end.Rating.mean(), 4) if len(at_end) else None,
        **{name: at_end[col].value_counts().sort_index().to_dict() for name, col in SPLITS.items()},
        "headcount_by_month": hc[(hc.Year == year) & hc.Month.isin(months)].groupby("Month").size().to_dict(),
        "headcount_by_month_was": (hc[(hc.Year == year - 1) & hc.Month.isin(months)].groupby("Month").size().to_dict()
                                   if comparable else {}),
        "turnover_by_department": by_dept[by_dept.avg > 0].turnover.round(4).to_dict(),
        "recent_hires": [{"employee": int(r.EmpID), "department": r.Department, "title": r.Title,
                          "joined": r.Date.strftime("%Y-%m-%d")} for r in hires.itertuples()],
    }


if __name__ == "__main__":
    yr = int(sys.argv[1]) if len(sys.argv) > 1 else 2023
    print(json.dumps(expected(yr, dict(a.split("=", 1) for a in sys.argv[2:])), indent=2))
