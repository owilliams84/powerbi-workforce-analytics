"""Recompute the headline measures in pandas and diff them against what the model returns.

The model is the thing being checked, so the check cannot use it. This reads data/ straight
from the CSVs, computes the same ten figures by year, by department and in total, and compares
them to the CSV that etl/checks/verify.dax produced against the live model.

    powershell -File etl/query_model.ps1 -DaxFile etl/checks/verify.dax -Csv > etl/checks/dax_actual.csv
    python etl/verify_measures.py

Non-zero exit means a measure and its pandas equivalent disagree.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ACTUAL = ROOT / "etl" / "checks" / "dax_actual.csv"

FIELDS = ["joiners", "leavers", "early", "headcount", "avg_headcount", "engagement", "surveys",
          "training_cost", "completion", "cost_outside"]
TOL = {"avg_headcount": 1e-3, "engagement": 1e-5, "completion": 1e-5,
       "training_cost": 0.011, "cost_outside": 0.011}


def load():
    emp = pd.read_csv(DATA / "dim_employee.csv")
    hc = pd.read_csv(DATA / "fact_headcount.csv", parse_dates=["Date"])
    mv = pd.read_csv(DATA / "fact_movement.csv", parse_dates=["Date"])
    eng = pd.read_csv(DATA / "fact_engagement.csv", parse_dates=["Date"])
    tr = pd.read_csv(DATA / "fact_training.csv", parse_dates=["Date"])
    dept = emp.set_index("EmpID")["Department"]
    early = emp.set_index("EmpID")["EarlyLeaver"]
    for df in (hc, mv, eng, tr):
        df["Department"] = df["EmpID"].map(dept)
        df["Year"] = df["Date"].dt.year
    mv["Early"] = mv["EmpID"].map(early)
    return hc, mv, eng, tr


def figures(hc, mv, eng, tr, all_snapshots) -> dict:
    """all_snapshots: the month-ends in view, whether or not this slice has anyone at them -
    [Average Headcount] counts an empty month as zero, so pandas must too."""
    counts = hc.groupby("Date").size().reindex(all_snapshots, fill_value=0)
    last = all_snapshots.max()
    joiners = int((mv.Movement == "Joiner").sum())
    lv = mv[mv.Movement == "Leaver"]
    e_in = eng[eng.InEmployment == "Yes"]
    t_in = tr[tr.InEmployment == "Yes"]
    return dict(
        joiners=joiners,
        leavers=len(lv),
        early=int((lv.Early == "Yes").sum()),
        headcount=int((hc.Date == last).sum()),
        avg_headcount=round(float(counts.mean()), 4),
        engagement=round(float(e_in.Engagement.mean()), 6) if len(e_in) else 0.0,
        surveys=len(e_in),
        training_cost=round(float(t_in.Cost.sum()), 2),
        completion=round(float(t_in.Outcome.isin(["Completed", "Passed"]).mean()), 6)
        if len(t_in) else 0.0,
        cost_outside=round(float(tr.loc[tr.InEmployment == "No", "Cost"].sum()), 2),
    )


def main() -> None:
    if not ACTUAL.exists():
        print(f"missing {ACTUAL} - run query_model.ps1 against the live model first")
        sys.exit(2)
    actual = pd.read_csv(ACTUAL)
    actual.columns = [c.strip("[]") for c in actual.columns]
    actual["key"] = actual["key"].astype(str)

    hc, mv, eng, tr = load()
    snaps = pd.DatetimeIndex(sorted(hc.Date.unique()))
    rows = [dict(grain="all", key="all", **figures(hc, mv, eng, tr, snaps))]
    for y in sorted(set(mv.Year) | set(hc.Year)):
        s = snaps[snaps.year == y]
        if len(s) == 0:
            continue
        rows.append(dict(grain="year", key=str(y), **figures(
            hc[hc.Year == y], mv[mv.Year == y], eng[eng.Year == y], tr[tr.Year == y], s)))
    for d in sorted(hc.Department.dropna().unique()):
        rows.append(dict(grain="department", key=d, **figures(
            hc[hc.Department == d], mv[mv.Department == d], eng[eng.Department == d],
            tr[tr.Department == d], snaps)))
    expected = pd.DataFrame(rows)

    merged = expected.merge(actual, on=["grain", "key"], how="outer",
                            suffixes=("_pandas", "_dax"), indicator="side")
    problems = [f"{r.grain}/{r.key}: present in {r.side} only"
                for r in merged[merged["side"] != "both"].itertuples()]
    both = merged[merged["side"] == "both"]
    for field in FIELDS:
        a = both[f"{field}_pandas"].astype(float)
        # A DAX BLANK lands here as NaN; it means zero. Fill it, because NaN > tol is False and
        # would let a genuine mismatch through as a pass.
        b = both[f"{field}_dax"].astype(float).fillna(0.0)
        bad = (a - b).abs() > TOL.get(field, 0.5)
        for r, av, bv in zip(both[bad].itertuples(), a[bad], b[bad]):
            problems.append(f"{r.grain}/{r.key} {field}: pandas={av} dax={bv}")

    print(f"{len(both)} rows compared across {len(FIELDS)} measures "
          f"({len(both) * len(FIELDS)} checks)")
    if problems:
        print("\nMISMATCHES")
        for p in problems:
            print("  " + p)
        sys.exit(1)
    print("every figure agrees")

    t = rows[0]
    print("\nheadline, recomputed from the CSVs:")
    print(f"  headcount at {snaps.max().date()}   {t['headcount']:,}")
    print(f"  joiners / leavers           {t['joiners']:,} / {t['leavers']:,}")
    print(f"  left in year one            {t['early']:,} ({t['early'] / t['leavers']:.1%})")
    print(f"  engagement (in employment)  {t['engagement']:.3f}")
    print(f"  training cost, not employed ${t['cost_outside']:,.2f}")
    yearly = expected[expected.grain == "year"].set_index("key")
    print("  headcount at each year's last month-end: "
          + ", ".join(f"{k} {int(v):,}" for k, v in yearly.headcount.items()))
    print("  annualised turnover by year: "
          + ", ".join(f"{k} {r.leavers * 12 / (r.avg_headcount * len(snaps[snaps.year == int(k)])):.1%}"
                      for k, r in yearly.iterrows()))


if __name__ == "__main__":
    main()
