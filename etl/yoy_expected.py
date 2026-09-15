"""Expected figures for page 05, Year on Year, computed in pandas from the star schema.

The page compares a year with the same months of an earlier one. "The same months" means the
month-ends the chosen year actually has a headcount snapshot for - January to December for 2019
to 2022, January to July for 2023. The comparison exists only when the earlier year has a
snapshot for every one of those months, so 2019 against 2018 (August to December only) has
nothing to compare with.

    python etl/yoy_expected.py                        # 2023 against the prior year
    python etl/yoy_expected.py 2023 two               # 2023 against 2021
    python etl/yoy_expected.py 2023 prior "Business Unit=NEL"
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data"
TOP_N = 8
COLUMN_OF = {"Business Unit": "BusinessUnit", "Employee Type": "EmployeeType"}


def load(panel: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, set]:
    emp = pd.read_csv(DATA / "dim_employee.csv")
    hc = pd.read_csv(DATA / "fact_headcount.csv", parse_dates=["Date"])
    mv = pd.read_csv(DATA / "fact_movement.csv", parse_dates=["Date"])
    # Snapshot months come from every employee: the panel narrows people, not the calendar.
    snapshots = {(d.year, d.month) for d in hc.Date.unique().astype("datetime64[ns]").tolist()
                 for d in [pd.Timestamp(d)]}
    for field, value in panel.items():
        emp = emp[emp[COLUMN_OF[field]] == value]
    keep = ["EmpID", "Department", "Division", "EarlyLeaver"]
    hc = hc.merge(emp[keep], on="EmpID")
    mv = mv.merge(emp[keep], on="EmpID")
    for df in (hc, mv):
        df["Year"] = df.Date.dt.year
        df["Month"] = df.Date.dt.month
    return hc, mv, emp, snapshots


def months_of(snapshots: set, year: int) -> list[int]:
    return sorted(m for y, m in snapshots if y == year)


def period(hc: pd.DataFrame, mv: pd.DataFrame, year: int, months: list[int], key: str | None = None):
    """Headcount at the last month-end, average headcount, joiners, leavers, early leavers and
    annualised turnover - overall, or grouped by `key`."""
    h = hc[(hc.Year == year) & hc.Month.isin(months)]
    m = mv[(mv.Year == year) & mv.Month.isin(months)]
    last = max(months)
    groups = [key] if key else []

    def count(df, name):
        return (df.groupby(groups).size() if key else pd.Series({"all": len(df)})).rename(name)

    by_month = h.groupby(groups + ["Month"]).size() if key else h.groupby("Month").size()
    if key:
        avg = by_month.unstack(fill_value=0).reindex(columns=months, fill_value=0).mean(axis=1).rename("avg")
    else:
        avg = pd.Series({"all": by_month.reindex(months, fill_value=0).mean()}, name="avg")
    out = pd.concat([
        count(h[h.Month == last], "headcount"), avg,
        count(m[m.Movement == "Joiner"], "joiners"), count(m[m.Movement == "Leaver"], "leavers"),
        count(m[(m.Movement == "Leaver") & (m.EarlyLeaver == "Yes")], "early"),
    ], axis=1).fillna(0)
    out["turnover"] = out.leavers * 12 / (out.avg * len(months))
    return out


def main() -> None:
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2023
    offset = 2 if len(sys.argv) > 2 and sys.argv[2].startswith("two") else 1
    panel = dict(a.split("=", 1) for a in sys.argv[3:])
    hc, mv, emp, snapshots = load(panel)

    comp_year = year - offset
    months = months_of(snapshots, year)
    comp_months = months_of(snapshots, comp_year)
    available = bool(comp_months) and set(months) <= set(comp_months)
    out: dict = {"year": year, "comparison_year": comp_year, "panel": panel,
                 "months": [min(months), max(months)], "available": available}

    a = period(hc, mv, year, months).iloc[0]
    out["actual"] = {k: round(float(v), 4) for k, v in a.items()}
    out["actual"]["early_share"] = round(a.early / a.leavers, 4) if a.leavers else None
    if not available:
        print(json.dumps(out, indent=2))
        return

    c = period(hc, mv, comp_year, months).iloc[0]
    out["comparison"] = {k: round(float(v), 4) for k, v in c.items()}
    out["comparison"]["early_share"] = round(c.early / c.leavers, 4) if c.leavers else None

    monthly = []
    for mth in months:
        ra = period(hc, mv, year, [mth]).iloc[0]
        rc = period(hc, mv, comp_year, [mth]).iloc[0]
        monthly.append({"month": mth, **{f"{k}": int(ra[k]) for k in ("headcount", "joiners", "leavers")},
                        **{f"{k}_comp": int(rc[k]) for k in ("headcount", "joiners", "leavers")}})
    out["monthly"] = monthly

    da, dc = period(hc, mv, year, months, "Department"), period(hc, mv, comp_year, months, "Department")
    dept = da.join(dc, rsuffix="_comp", how="outer").fillna(0)
    dept = dept[(dept.avg > 0) | (dept.avg_comp > 0)]
    dept["change_pp"] = (dept.turnover - dept.turnover_comp) * 100
    dept = dept.sort_values("change_pp", ascending=False)
    out["departments"] = [{"name": k, "headcount": int(r.headcount), "leavers": int(r.leavers),
                           "leavers_comp": int(r.leavers_comp), "turnover": round(r.turnover, 4),
                           "turnover_comp": round(r.turnover_comp, 4), "change_pp": round(r.change_pp, 2)}
                          for k, r in dept.iterrows()]
    out["departments_up"] = int((dept.change_pp > 0).sum())

    va, vc = period(hc, mv, year, months, "Division"), period(hc, mv, comp_year, months, "Division")
    div = va[["leavers"]].join(vc[["leavers"]], rsuffix="_comp", how="outer").fillna(0)
    div = div[(div.leavers > 0) | (div.leavers_comp > 0)]
    div["change"] = div.leavers - div.leavers_comp
    div = div.rename_axis("name").reset_index()
    # The model's tiebreaks: more leavers first on Top, fewer on Bottom; then name - A-Z on Top,
    # Z-A on Bottom (one composite number ranked in two directions).
    div = div.sort_values(["change", "leavers", "name"], ascending=[False, False, True]).set_index("name")

    def rows(df):
        return [{"name": k, "leavers": int(r.leavers), "leavers_comp": int(r.leavers_comp),
                 "change": int(r.change)} for k, r in df.iterrows()]

    out["divisions_in_play"] = len(div)
    out["divisions_up"] = int((div.change > 0).sum())
    out["divisions_top"] = rows(div.head(TOP_N))
    out["divisions_bottom"] = rows(div.iloc[::-1].head(TOP_N))
    out["divisions_all"] = rows(div)
    out["max_abs_division_change"] = int(div.change.abs().max())
    out["max_abs_department_pp"] = round(float(dept.change_pp.abs().max()), 2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
