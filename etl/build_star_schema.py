"""Turn the four HR files into a workforce star schema, and say what was wrong with them.

Source: https://www.kaggle.com/datasets/ravindrasinghrana/employeedataset - "Employee/HR Dataset
(All in One)", CC0 public domain. 3,000 employees, one engagement survey and one training record
per employee, and 3,000 job applicants. Synthetic.

    python etl/build_star_schema.py [--source <folder with the four CSVs>]

With --source the four files are copied into data/source/ first (they are CC0, so they are
committed); without it the build reads data/source/. Writes data/ and data/quality_report.json.

Three decisions worth reading before the numbers:

1.  **Employment status comes from the dates, not the status field.** The HR-system status
    contradicts the exit date for 1,146 employees - 991 of them are "Active" with an exit date,
    and every "Future Start" started years ago and has since left. The model derives status from
    start and exit dates and keeps the source label beside it, so the conflict stays visible
    rather than being tidied away.

2.  **Recruitment is left out.** Applicant IDs run 1001-4000, exactly like employee IDs, and
    join perfectly - to the wrong people. Not one of 3,000 applicant names matches the employee
    holding the same ID, not one applicant's job title exists in the company, and every
    applicant pairs a US state with a non-US country. The file is tested, the results go in the
    quality report, and nothing from it reaches the model.

3.  **Events are tested against the employment they belong to.** A third of surveys and training
    records are dated after the person left, and about a tenth before they started. Every event
    carries an "In employment" flag, and the measures report on in-employment events by default
    with the naive figure available beside them.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SRC = DATA / "source"
LF = "\n"

FILES = ["employee_data.csv", "employee_engagement_survey_data.csv",
         "recruitment_data.csv", "training_and_development_data.csv"]


def write_csv(df: pd.DataFrame, name: str) -> None:
    path = DATA / name
    df.to_csv(path, index=False, lineterminator=LF)
    print("  %-28s %8d rows  %7.1f KB" % (name, len(df), path.stat().st_size / 1024))


def band(value, edges, labels):
    if pd.isna(value):
        return None, None
    for i, edge in enumerate(edges):
        if value < edge:
            return labels[i], i
    return labels[-1], len(edges)


def day_first_proven(s: pd.Series) -> dict:
    """A dd-mm-yyyy field is only provably day-first if the first number ever exceeds 12 and the
    second never does. Recorded rather than assumed, because a US-default parser reads 03-08-2023
    as March and nothing errors."""
    p = s.dropna().str.extract(r"^(\d{1,2})-(\d{1,2})-(\d{4})$").astype(float)
    return {"first_over_12": int((p[0] > 12).sum()), "second_over_12": int((p[1] > 12).sum()),
            "day_first": bool((p[0] > 12).any() and not (p[1] > 12).any())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", help="folder holding the four Kaggle CSVs to copy in")
    args = ap.parse_args()
    DATA.mkdir(exist_ok=True)
    SRC.mkdir(exist_ok=True)
    if args.source:
        for f in FILES:
            shutil.copyfile(Path(args.source) / f, SRC / f)

    e = pd.read_csv(SRC / "employee_data.csv", dtype=str)
    g = pd.read_csv(SRC / "employee_engagement_survey_data.csv", dtype=str)
    r = pd.read_csv(SRC / "recruitment_data.csv", dtype=str)
    t = pd.read_csv(SRC / "training_and_development_data.csv", dtype=str)

    q: dict[str, object] = {"source_rows": {"employees": len(e), "surveys": len(g),
                                            "applicants": len(r), "training": len(t)}}

    # Whitespace: DepartmentType carries trailing spaces on every Production row, so a trimmed
    # "Production" from any other source would become a second, separate department.
    ws = {c: int((e[c].dropna().str.len() != e[c].dropna().str.strip().str.len()).sum())
          for c in e.columns}
    q["untrimmed_values"] = {k: v for k, v in ws.items() if v}
    for c in e.columns:
        e[c] = e[c].str.strip()

    q["date_format"] = {"DOB": day_first_proven(e["DOB"]),
                        "Survey Date": day_first_proven(g["Survey Date"])}

    e["Start"] = pd.to_datetime(e["StartDate"], format="%d-%b-%y")
    e["Exit"] = pd.to_datetime(e["ExitDate"], format="%d-%b-%y")
    e["Born"] = pd.to_datetime(e["DOB"], format="%d-%m-%Y")
    g["Date"] = pd.to_datetime(g["Survey Date"], format="%d-%m-%Y")
    t["Date"] = pd.to_datetime(t["Training Date"], format="%d-%b-%y")
    r["Date"] = pd.to_datetime(r["Application Date"], format="%d-%b-%y")

    as_at = max(e["Start"].max(), e["Exit"].max(), g["Date"].max(), t["Date"].max(),
                r["Date"].max())
    q["as_at"] = str(as_at.date())
    q["exit_before_start"] = int((e["Exit"] < e["Start"]).sum())

    # ------------------------------------------------------------------ status, from the dates
    left = e["Exit"].notna() & (e["Exit"] <= as_at)
    e["Status"] = np.where(left, "Left", "Employed")
    contradicts = (left & e["EmployeeStatus"].isin(["Active", "Leave of Absence", "Future Start"])) | \
                  (~left & e["EmployeeStatus"].isin(["Voluntarily Terminated", "Terminated for Cause"]))
    e["StatusCheck"] = np.where(contradicts, "Contradicts dates", "Agrees with dates")
    q["status_conflicts"] = int(contradicts.sum())
    q["status_conflicts_by_label"] = e.loc[contradicts, "EmployeeStatus"].value_counts().to_dict()

    # TerminationType is "Unk" for everyone still employed, and the four real reasons overlap:
    # a resignation is voluntary. Kept as the source reported it, blanked where nobody left.
    e["Leaver Reason"] = np.where(left, e["TerminationType"], "")
    e["Leaver Group"] = e["Leaver Reason"].map(
        {"Voluntary": "Voluntary", "Resignation": "Voluntary", "Involuntary": "Involuntary",
         "Retirement": "Retirement", "": ""})
    q["termination_types"] = e.loc[left, "TerminationType"].value_counts().to_dict()

    tenure = (e["Exit"].where(left, as_at) - e["Start"]).dt.days / 365.25
    age = (as_at - e["Born"]).dt.days / 365.25
    q["leavers_within_first_year"] = int(((tenure < 1) & left).sum())
    q["leavers"] = int(left.sum())

    # ------------------------------------------------------------------ recruitment linkage test
    m = e.merge(r, left_on="EmpID", right_on="Applicant ID")
    same_name = ((m["FirstName"].str.lower() == m["First Name"].str.strip().str.lower()) &
                 (m["LastName"].str.lower() == m["Last Name"].str.strip().str.lower()))
    q["recruitment_id_collision"] = {"ids_matching_employees": int(len(m)),
                                     "same_person_by_name": int(same_name.sum())}
    q["recruitment_state_country_conflict"] = int(((r["State"].str.len() == 2) &
                                                   (r["Country"] != "United States")).sum())
    q["recruitment_countries"] = int(r["Country"].nunique())
    q["applicant_titles_not_in_company"] = int((~r["Job Title"].isin(set(e["Title"]))).sum())

    # ------------------------------------------------------------------ managers, without names
    # Supervisor is a person's name. Span of control is worth reporting; the name is not, so each
    # supervisor becomes an opaque key in the order they first appear.
    sup = {name: f"M{i:03d}" for i, name in enumerate(pd.unique(e["Supervisor"]), start=1)}
    e["ManagerKey"] = e["Supervisor"].map(sup)
    q["managers"] = len(sup)
    q["dropped_columns_employee"] = ["FirstName", "LastName", "ADEmail", "Supervisor", "DOB",
                                     "MaritalDesc", "LocationCode"]

    age_bands = ([25, 35, 45, 55], ["Under 25", "25-34", "35-44", "45-54", "55+"])
    ten_bands = ([1, 2, 3, 5], ["Under 1 year", "1-2 years", "2-3 years", "3-5 years", "5+ years"])
    rows = []
    for i, x in e.iterrows():
        ab, abs_ = band(age[i], *age_bands)
        tb, tbs = band(tenure[i], *ten_bands)
        rows.append(dict(
            EmpID=int(x.EmpID), Title=x.Title, ManagerKey=x.ManagerKey,
            BusinessUnit=x.BusinessUnit, Department=x.DepartmentType, Division=x.Division,
            JobFunction=x.JobFunctionDescription, EmployeeType=x.EmployeeType,
            Classification=x.EmployeeClassificationType, PayZone=x.PayZone, State=x.State,
            Gender=x.GenderCode, Ethnicity=x.RaceDesc,
            AgeBand=ab, AgeBandSort=abs_, TenureBand=tb, TenureBandSort=tbs,
            TenureYears=round(float(tenure[i]), 3),
            Performance=x["Performance Score"], Rating=int(x["Current Employee Rating"]),
            StartDate=x.Start.date().isoformat(),
            ExitDate=x.Exit.date().isoformat() if left[i] else "",
            Status=x.Status, SourceStatus=x.EmployeeStatus, StatusCheck=x.StatusCheck,
            LeaverReason=x["Leaver Reason"], LeaverGroup=x["Leaver Group"],
            EarlyLeaver="Yes" if left[i] and tenure[i] < 1 else "No",
        ))
    dim_employee = pd.DataFrame(rows).sort_values("EmpID")

    # ------------------------------------------------------------------ date
    start = e["Start"].min().to_period("M").start_time
    end = as_at.to_period("M").end_time.normalize()
    days = pd.date_range(start, end, freq="D")
    dd = pd.DataFrame({"Date": days})
    d = dd["Date"]
    dd["Year"] = d.dt.year
    dd["Quarter"] = "Q" + d.dt.quarter.astype(str)
    dd["MonthNumber"] = d.dt.month
    dd["MonthName"] = d.dt.strftime("%B")
    dd["MonthShort"] = d.dt.strftime("%b")
    dd["MonthYear"] = d.dt.strftime("%b %Y")
    dd["MonthYearSort"] = d.dt.year * 100 + d.dt.month
    dd["MonthStart"] = d.dt.to_period("M").dt.start_time.dt.date
    dd["IsMonthEnd"] = np.where(d.dt.is_month_end, "Yes", "No")
    dd["Date"] = d.dt.date
    q["calendar"] = {"from": str(days.min().date()), "to": str(days.max().date())}

    # ------------------------------------------------------------------ headcount snapshot
    # One row per employee per month-end they were employed at. Headcount is a stock, so it is
    # read at a point in time; summing it across months is meaningless, and the model only ever
    # takes it at the last month-end in view.
    month_ends = pd.date_range(start, as_at, freq="ME")
    snap = []
    for me in month_ends:
        on = (e["Start"] <= me) & (e["Exit"].isna() | (e["Exit"] > me))
        snap.append(pd.DataFrame({"Date": me.date().isoformat(),
                                  "EmpID": e.loc[on, "EmpID"].astype(int)}))
    fact_headcount = pd.concat(snap, ignore_index=True)

    # ------------------------------------------------------------------ joiners and leavers
    joins = pd.DataFrame({"Date": e["Start"].dt.date.astype(str), "EmpID": e["EmpID"].astype(int),
                          "Movement": "Joiner"})
    leaves = pd.DataFrame({"Date": e.loc[left, "Exit"].dt.date.astype(str),
                           "EmpID": e.loc[left, "EmpID"].astype(int), "Movement": "Leaver"})
    fact_movement = pd.concat([joins, leaves], ignore_index=True).sort_values(["Date", "EmpID"])

    # ------------------------------------------------------------------ events vs employment
    emp = e.set_index(e["EmpID"].astype(int))[["Start", "Exit"]]

    def in_employment(ids: pd.Series, dates: pd.Series) -> pd.Series:
        s = emp.loc[ids.astype(int), "Start"].to_numpy()
        x = emp.loc[ids.astype(int), "Exit"].to_numpy()
        ok = (dates.to_numpy() >= s) & (pd.isna(x) | (dates.to_numpy() <= x))
        return pd.Series(np.where(ok, "Yes", "No"), index=ids.index)

    g["InEmployment"] = in_employment(g["Employee ID"], g["Date"])
    t["InEmployment"] = in_employment(t["Employee ID"], t["Date"])
    for name, df in (("surveys", g), ("training", t)):
        ids = df["Employee ID"].astype(int)
        s, x = emp.loc[ids, "Start"].to_numpy(), emp.loc[ids, "Exit"].to_numpy()
        q[f"{name}_outside_employment"] = {
            "before_start": int((df["Date"].to_numpy() < s).sum()),
            "after_exit": int((~pd.isna(x) & (df["Date"].to_numpy() > x)).sum()),
            "in_employment": int((df["InEmployment"] == "Yes").sum()),
        }

    fact_engagement = pd.DataFrame({
        "Date": g["Date"].dt.date.astype(str), "EmpID": g["Employee ID"].astype(int),
        "Engagement": g["Engagement Score"].astype(int),
        "Satisfaction": g["Satisfaction Score"].astype(int),
        "WorkLifeBalance": g["Work-Life Balance Score"].astype(int),
        "InEmployment": g["InEmployment"]})

    programs = sorted(t["Training Program Name"].str.strip().unique())
    dim_program = pd.DataFrame({"ProgramKey": range(1, len(programs) + 1), "Program": programs})
    pkey = dict(zip(dim_program["Program"], dim_program["ProgramKey"]))
    fact_training = pd.DataFrame({
        "Date": t["Date"].dt.date.astype(str), "EmpID": t["Employee ID"].astype(int),
        "ProgramKey": t["Training Program Name"].str.strip().map(pkey),
        "TrainingType": t["Training Type"].str.strip(),
        "Outcome": t["Training Outcome"].str.strip(),
        "Days": t["Training Duration(Days)"].astype(int),
        "Cost": t["Training Cost"].astype(float).round(2),
        "InEmployment": t["InEmployment"]})
    q["dropped_columns_training"] = ["Location", "Trainer"]

    # Recruitment is tested above and then left out. It fails every test that would make it
    # this company's pipeline: the IDs collide with employees but the names never match, not one
    # applicant's job title exists anywhere in the company, and every applicant pairs a US state
    # with a non-US country. A funnel built on it would be a funnel of someone else's vacancies.
    q["recruitment_excluded"] = True
    q["training_cost"] = {
        "all_records": round(float(t["Training Cost"].astype(float).sum()), 2),
        "outside_employment": round(float(
            t.loc[t["InEmployment"] == "No", "Training Cost"].astype(float).sum()), 2)}

    print("data/")
    write_csv(dd, "dim_date.csv")
    write_csv(dim_employee, "dim_employee.csv")
    write_csv(dim_program, "dim_program.csv")
    write_csv(fact_headcount, "fact_headcount.csv")
    write_csv(fact_movement, "fact_movement.csv")
    write_csv(fact_engagement, "fact_engagement.csv")
    write_csv(fact_training, "fact_training.csv")
    stale = DATA / "fact_recruitment.csv"
    if stale.exists():
        stale.unlink()

    # Headline figures the report and the write-up both quote, computed once, here.
    last = fact_headcount["Date"].max()
    q["headcount_at_as_at_month_end"] = int((fact_headcount["Date"] == last).sum())
    yr = pd.to_datetime(fact_movement["Date"]).dt.year
    q["joiners_by_year"] = fact_movement[fact_movement.Movement == "Joiner"].groupby(yr).size() \
        .astype(int).to_dict()
    q["leavers_by_year"] = fact_movement[fact_movement.Movement == "Leaver"].groupby(yr).size() \
        .astype(int).to_dict()
    q["engagement_mean"] = {"all_surveys": round(float(fact_engagement.Engagement.mean()), 4),
                            "in_employment": round(float(
                                fact_engagement.loc[fact_engagement.InEmployment == "Yes",
                                                    "Engagement"].mean()), 4)}
    (DATA / "quality_report.json").write_text(json.dumps(q, indent=2, default=str) + LF,
                                              encoding="utf-8", newline=LF)
    print("\ndata/quality_report.json")
    for k in ("as_at", "status_conflicts", "leavers", "leavers_within_first_year",
              "headcount_at_as_at_month_end", "recruitment_id_collision",
              "surveys_outside_employment", "training_outside_employment", "engagement_mean"):
        print("  %-32s %s" % (k, q[k]))


if __name__ == "__main__":
    main()
