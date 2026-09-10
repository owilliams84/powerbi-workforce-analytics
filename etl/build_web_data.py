"""Emit the JSON the milestonebi.com case study reads.

The case study redraws the Power BI report for the web, so its numbers have to be the same
numbers. They are computed here from data/ - the same CSVs the model loads - rather than typed
into the page, and verify_measures.py has already proved that those CSVs and the model agree.

    python etl/build_web_data.py [--out <path>]

Writes web/workforce-analytics.json.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "web" / "workforce-analytics.json"


def r(v, dp=2):
    return None if pd.isna(v) else round(float(v), dp)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    emp = pd.read_csv(DATA / "dim_employee.csv")
    hc = pd.read_csv(DATA / "fact_headcount.csv", parse_dates=["Date"])
    mv = pd.read_csv(DATA / "fact_movement.csv", parse_dates=["Date"])
    eng = pd.read_csv(DATA / "fact_engagement.csv", parse_dates=["Date"])
    tr = pd.read_csv(DATA / "fact_training.csv", parse_dates=["Date"])
    quality = json.loads((DATA / "quality_report.json").read_text(encoding="utf-8"))

    snaps = pd.DatetimeIndex(sorted(hc.Date.unique()))
    counts = hc.groupby("Date").size().reindex(snaps, fill_value=0)
    lv = mv[mv.Movement == "Leaver"].merge(emp, on="EmpID")
    jn = mv[mv.Movement == "Joiner"]

    out: dict = {}
    out["headcount_by_month"] = dict(months=[d.strftime("%Y-%m") for d in snaps],
                                     values=[int(v) for v in counts])

    # Rolling twelve-month turnover at each month-end: leavers in the twelve months to that
    # month-end over the average of the month-end headcounts in the same window - the
    # [Turnover 12M %] measure, recomputed.
    roll = []
    for i, me in enumerate(snaps):
        start = me - pd.DateOffset(months=12)
        window = counts[(counts.index > start) & (counts.index <= me)]
        leavers = int(((lv.Date > start) & (lv.Date <= me)).sum())
        roll.append(r(leavers / window.mean(), 4) if i >= 11 and window.mean() else None)
    out["turnover_12m"] = roll

    years = []
    for y in sorted(snaps.year.unique()):
        s = counts[counts.index.year == y]
        leavers = int((lv.Date.dt.year == y).sum())
        years.append(dict(
            year=int(y), months=int(len(s)), joiners=int((jn.Date.dt.year == y).sum()),
            leavers=leavers, headcount_end=int(s.iloc[-1]), avg_headcount=r(s.mean(), 1),
            turnover_annualised=r(leavers * 12 / (s.mean() * len(s)), 4),
        ))
    out["by_year"] = years

    tenure = (lv.groupby(["TenureBand", "TenureBandSort"]).size().reset_index(name="leavers")
                .sort_values("TenureBandSort"))
    out["leavers_by_tenure"] = [dict(band=b, leavers=int(n))
                                for b, n in zip(tenure.TenureBand, tenure.leavers)]
    out["leavers_by_group"] = lv.LeaverGroup.value_counts().to_dict()

    e_in = eng[eng.InEmployment == "Yes"]
    t_in = tr[tr.InEmployment == "Yes"]
    out["totals"] = dict(
        employees=int(len(emp)), leavers=int(len(lv)), joiners=int(len(jn)),
        headcount_last=int(counts.iloc[-1]), last_snapshot=snaps.max().strftime("%Y-%m-%d"),
        peak_headcount=int(counts.max()), peak_month=counts.idxmax().strftime("%Y-%m"),
        early_leavers=int((lv.EarlyLeaver == "Yes").sum()),
        median_tenure_exit=r(lv.TenureYears.median(), 2),
        engagement_in=r(e_in.Engagement.mean(), 3), engagement_all=r(eng.Engagement.mean(), 3),
        completion=r(t_in.Outcome.isin(["Completed", "Passed"]).mean(), 4),
        training_cost_all=r(tr.Cost.sum()),
        training_cost_outside=r(tr.loc[tr.InEmployment == "No", "Cost"].sum()),
        status_conflicts=quality["status_conflicts"],
    )

    by_dept = []
    last = snaps.max()
    for d, g in emp.groupby("Department"):
        ids = set(g.EmpID)
        s = hc[hc.EmpID.isin(ids)].groupby("Date").size().reindex(snaps, fill_value=0)
        n_leave = int(lv.EmpID.isin(ids).sum())
        by_dept.append(dict(
            department=d, headcount=int((hc[(hc.Date == last)].EmpID.isin(ids)).sum()),
            leavers=n_leave,
            turnover_annualised=r(n_leave * 12 / (s.mean() * len(s)), 4) if s.mean() else None,
            early_share=r((lv[lv.EmpID.isin(ids)].EarlyLeaver == "Yes").mean(), 4),
        ))
    out["by_department"] = sorted(by_dept, key=lambda x: -x["headcount"])

    out["quality"] = {k: quality[k] for k in (
        "as_at", "status_conflicts", "status_conflicts_by_label", "recruitment_id_collision",
        "recruitment_state_country_conflict", "applicant_titles_not_in_company",
        "surveys_outside_employment", "training_outside_employment", "untrimmed_values",
        "date_format", "termination_types", "training_cost",
    )}

    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, separators=(",", ":")) + "\n",
                    encoding="utf-8", newline="\n")
    print(f"{path} {path.stat().st_size / 1024:.1f} KB")
    t = out["totals"]
    print(f"  peak headcount {t['peak_headcount']:,} in {t['peak_month']}; "
          f"{t['headcount_last']:,} at {t['last_snapshot']}")
    print("  annualised turnover: " + ", ".join(
        f"{y['year']} {y['turnover_annualised']:.1%}" for y in years))


if __name__ == "__main__":
    main()
