"""Generate the TMDL semantic model - tables, relationships, measures.

TMDL is indentation-sensitive (tabs) and forbids blank lines inside an object, and every object
needs a stable lineageTag. This owns the format and the tags (uuid5 of the object's path, so
re-running never churns them), and the table definitions below read as a schema.

    python etl/build_model.py            # partitions read the CSVs from GitHub over HTTPS
    python etl/build_model.py --local    # partitions read data/ on this machine (offline)

Rewrites <model>/definition/ from scratch every run.
"""

from __future__ import annotations

import argparse
import shutil
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "Workforce Analytics.SemanticModel"
DEFN = MODEL / "definition"
DATA = ROOT / "data"

RAW = "https://raw.githubusercontent.com/owilliams84/powerbi-workforce-analytics/main/data/"
NS = uuid.UUID("3b8e1f52-7c40-4d9a-a61e-5f2c9d8b7e13")


def tag(*parts: str) -> str:
    return str(uuid.uuid5(NS, "workforce:" + ":".join(parts)))


def q(name: str) -> str:
    """Quote a TMDL identifier when it needs it."""
    return name if name.replace("_", "").isalnum() else f"'{name}'"


def doc(text: str | None, indent: int) -> list[str]:
    if not text:
        return []
    pad = "\t" * indent
    return [f"{pad}/// {para}".rstrip() for para in text.strip("\n").split("\n")]


def col(name, source, dtype, **o):
    return dict(name=name, source=source, dtype=dtype, **o)


INT_T, TXT_T, NUM_T, DATE_T = "Int64.Type", "type text", "type number", "type date"

TABLES = {
    "Date": dict(
        file="dim_date.csv", date_table=True,
        doc="One row per day from 1 August 2018 to 31 August 2023, contiguous, and marked as the\n"
            "date table so DATESINPERIOD has a calendar to walk.\n"
            "\n"
            "The file's last event is 6 August 2023, so 2023 holds seven complete months and\n"
            "2018 holds five. The turnover measures annualise over the months actually in view\n"
            "rather than assuming twelve.",
        columns=[
            col("Date", "Date", "dateTime", key=True, format="d mmm yyyy"),
            col("Year", "Year", "int64", format="0"),
            col("Quarter", "Quarter", "string"),
            col("Month No", "MonthNumber", "int64", hidden=True, format="0"),
            col("Month", "MonthName", "string", sortBy="Month No"),
            col("Month Short", "MonthShort", "string", sortBy="Month No"),
            col("Month Year", "MonthYear", "string", sortBy="Month Year Sort"),
            col("Month Year Sort", "MonthYearSort", "int64", hidden=True, format="0"),
            col("Month Start", "MonthStart", "dateTime", format="mmm yyyy",
                doc="First day of the month, for a continuous monthly axis."),
            col("Is Month End", "IsMonthEnd", "string"),
        ],
        types={"Date": DATE_T, "Year": INT_T, "Quarter": TXT_T, "MonthNumber": INT_T,
               "MonthName": TXT_T, "MonthShort": TXT_T, "MonthYear": TXT_T,
               "MonthYearSort": INT_T, "MonthStart": DATE_T, "IsMonthEnd": TXT_T},
    ),
    "Employee": dict(
        file="dim_employee.csv", nullable=["ExitDate"],
        doc="One row per person who has ever worked here - 3,000 of them, 1,533 since gone.\n"
            "\n"
            "Names, email, supervisor name, date of birth, marital status and location code are\n"
            "dropped in the ETL. Age survives only as a band, and the supervisor as an opaque\n"
            "manager key, which is enough for span of control and nothing more.\n"
            "\n"
            "'Status' is derived from the start and exit dates. 'Source Status' is what the HR\n"
            "system said, and 'Status Check' records where the two disagree - 1,146 people, 991\n"
            "of them marked Active with an exit date already passed.",
        columns=[
            col("Employee", "EmpID", "int64", key=True, format="0",
                doc="The employee id. No names travel with it."),
            col("Title", "Title", "string"),
            col("Manager Key", "ManagerKey", "string", hidden=True),
            col("Business Unit", "BusinessUnit", "string"),
            col("Department", "Department", "string",
                doc="Trimmed in the ETL: every Production row in the source carries a trailing\n"
                    "space, which would make 'Production' two departments."),
            col("Division", "Division", "string"),
            col("Job Function", "JobFunction", "string"),
            col("Employee Type", "EmployeeType", "string"),
            col("Classification", "Classification", "string"),
            col("Pay Zone", "PayZone", "string"),
            col("State", "State", "string"),
            col("Gender", "Gender", "string"),
            col("Ethnicity", "Ethnicity", "string"),
            col("Age Band", "AgeBand", "string", sortBy="Age Band Sort",
                doc="Age at 6 August 2023, the file's as-at date."),
            col("Age Band Sort", "AgeBandSort", "int64", hidden=True, format="0"),
            col("Tenure Band", "TenureBand", "string", sortBy="Tenure Band Sort",
                doc="Service to the exit date for a leaver, to the as-at date for everyone else."),
            col("Tenure Band Sort", "TenureBandSort", "int64", hidden=True, format="0"),
            col("Tenure Years", "TenureYears", "double", format="0.00"),
            col("Performance", "Performance", "string"),
            col("Rating", "Rating", "int64", format="0"),
            col("Start Date", "StartDate", "dateTime", format="d mmm yyyy"),
            col("Exit Date", "ExitDate", "dateTime", format="d mmm yyyy"),
            col("Status", "Status", "string",
                doc="Employed or Left, from the dates - the model's version of the truth."),
            col("Source Status", "SourceStatus", "string",
                doc="The HR system's employment status, kept so the conflict stays visible."),
            col("Status Check", "StatusCheck", "string"),
            col("Leaver Reason", "LeaverReason", "string",
                doc="The source's termination type, blank for anyone still employed (the source\n"
                    "says 'Unk'). Voluntary and Resignation are separate values in the source\n"
                    "and mean the same thing; 'Leaver Group' merges them."),
            col("Leaver Group", "LeaverGroup", "string"),
            col("Early Leaver", "EarlyLeaver", "string",
                doc="Yes for anyone who left inside their first year."),
        ],
        types={"EmpID": INT_T, "Title": TXT_T, "ManagerKey": TXT_T, "BusinessUnit": TXT_T,
               "Department": TXT_T, "Division": TXT_T, "JobFunction": TXT_T,
               "EmployeeType": TXT_T, "Classification": TXT_T, "PayZone": TXT_T,
               "State": TXT_T, "Gender": TXT_T, "Ethnicity": TXT_T, "AgeBand": TXT_T,
               "AgeBandSort": INT_T, "TenureBand": TXT_T, "TenureBandSort": INT_T,
               "TenureYears": NUM_T, "Performance": TXT_T, "Rating": INT_T,
               "StartDate": DATE_T, "ExitDate": DATE_T, "Status": TXT_T,
               "SourceStatus": TXT_T, "StatusCheck": TXT_T, "LeaverReason": TXT_T,
               "LeaverGroup": TXT_T, "EarlyLeaver": TXT_T},
    ),
    "Program": dict(
        file="dim_program.csv",
        doc="The five training programmes in the file.",
        columns=[
            col("Program Key", "ProgramKey", "int64", key=True, hidden=True, format="0"),
            col("Program", "Program", "string"),
        ],
        types={"ProgramKey": INT_T, "Program": TXT_T},
    ),
    "Headcount": dict(
        file="fact_headcount.csv",
        doc="One row per employee per month-end they were employed at - a snapshot, not a flow.\n"
            "\n"
            "Headcount is a stock. Summing it across months counts the same person twelve times a\n"
            "year, so no measure here ever does: [Headcount] reads the last month-end in view and\n"
            "[Average Headcount] averages the month-ends.",
        columns=[
            col("Date", "Date", "dateTime", hidden=True, format="yyyy-mm-dd"),
            col("Employee Key", "EmpID", "int64", hidden=True, format="0"),
        ],
        types={"Date": DATE_T, "EmpID": INT_T},
    ),
    "Movement": dict(
        file="fact_movement.csv",
        doc="Joiners and leavers, one row per event, dated on the start or exit date.",
        columns=[
            col("Date", "Date", "dateTime", hidden=True, format="yyyy-mm-dd"),
            col("Employee Key", "EmpID", "int64", hidden=True, format="0"),
            col("Movement", "Movement", "string"),
        ],
        types={"Date": DATE_T, "EmpID": INT_T, "Movement": TXT_T},
    ),
    "Engagement": dict(
        file="fact_engagement.csv",
        doc="One engagement survey response per employee, August 2022 to August 2023.\n"
            "\n"
            "1,338 of the 3,000 responses are dated when the person did not work here - 287\n"
            "before they started and 1,051 after they left. 'In Employment' flags them, and the\n"
            "headline scores count in-employment responses only.",
        columns=[
            col("Date", "Date", "dateTime", hidden=True, format="yyyy-mm-dd"),
            col("Employee Key", "EmpID", "int64", hidden=True, format="0"),
            col("Engagement", "Engagement", "int64", hidden=True, format="0"),
            col("Satisfaction", "Satisfaction", "int64", hidden=True, format="0"),
            col("Work-Life Balance", "WorkLifeBalance", "int64", hidden=True, format="0"),
            col("In Employment", "InEmployment", "string"),
        ],
        types={"Date": DATE_T, "EmpID": INT_T, "Engagement": INT_T, "Satisfaction": INT_T,
               "WorkLifeBalance": INT_T, "InEmployment": TXT_T},
    ),
    "Training": dict(
        file="fact_training.csv",
        doc="One training record per employee, August 2022 to August 2023. Trainer and location\n"
            "are dropped: a trainer is a named person.\n"
            "\n"
            "1,317 records are dated outside the person's employment, and they carry $735,145 of\n"
            "the $1,675,886 training cost - 44%. Spend the organisation cannot attach to anyone\n"
            "who worked here at the time is a finding, not a rounding error.",
        columns=[
            col("Date", "Date", "dateTime", hidden=True, format="yyyy-mm-dd"),
            col("Employee Key", "EmpID", "int64", hidden=True, format="0"),
            col("Program Key", "ProgramKey", "int64", hidden=True, format="0"),
            col("Training Type", "TrainingType", "string"),
            col("Outcome", "Outcome", "string"),
            col("Days", "Days", "int64", hidden=True, format="0"),
            col("Cost", "Cost", "double", hidden=True, format="\\$#,0.00"),
            col("In Employment", "InEmployment", "string"),
        ],
        types={"Date": DATE_T, "EmpID": INT_T, "ProgramKey": INT_T, "TrainingType": TXT_T,
               "Outcome": TXT_T, "Days": INT_T, "Cost": NUM_T, "InEmployment": TXT_T},
    ),
}

RELATIONSHIPS = [
    ("Date to Headcount", "Headcount.Date", "Date.Date"),
    ("Employee to Headcount", "Headcount.'Employee Key'", "Employee.Employee"),
    ("Date to Movement", "Movement.Date", "Date.Date"),
    ("Employee to Movement", "Movement.'Employee Key'", "Employee.Employee"),
    ("Date to Engagement", "Engagement.Date", "Date.Date"),
    ("Employee to Engagement", "Engagement.'Employee Key'", "Employee.Employee"),
    ("Date to Training", "Training.Date", "Date.Date"),
    ("Employee to Training", "Training.'Employee Key'", "Employee.Employee"),
    ("Program to Training", "Training.'Program Key'", "Program.'Program Key'"),
]

USD, INT, PCT, DEC1, DEC2 = "\\$#,0", "#,0", "0.0%", "0.0", "0.00"

IN_EMP = "KEEPFILTERS('{t}'[In Employment] = \"Yes\")"
OUT_EMP = "KEEPFILTERS('{t}'[In Employment] = \"No\")"
SNAPSHOTS = "CALCULATETABLE(VALUES('Headcount'[Date]), REMOVEFILTERS('Employee'))"
LAST_12M = "DATESINPERIOD('Date'[Date], MAX('Date'[Date]), -12, MONTH)"

MEASURES = [
    # ---- stock
    ("Employees", "COUNTROWS('Employee')", INT,
     "Every employee record, whatever their dates. Not a headcount - see [Headcount]."),
    ("Snapshot Date", f"CALCULATE(MAX('Headcount'[Date]), REMOVEFILTERS('Employee'))",
     "d mmm yyyy", "The month-end [Headcount] is read at: the last one in view."),
    ("Headcount",
     "VAR LastSnapshot = [Snapshot Date]\n"
     "RETURN\n"
     "    CALCULATE(COUNTROWS('Headcount'), 'Date'[Date] = LastSnapshot)", INT,
     "People employed at the last month-end in view. A stock, so it is read at a point in time\n"
     "and never summed across months."),
    ("Months in View", f"COUNTROWS({SNAPSHOTS})", "0",
     "Month-end snapshots in the current filter - the denominator for annualising."),
    ("Average Headcount",
     "AVERAGEX(\n"
     f"    {SNAPSHOTS},\n"
     "    CALCULATE(COUNTROWS('Headcount')) + 0\n"
     ")", "#,0.0",
     "Mean of the month-end headcounts in view. The +0 counts a month where a department had\n"
     "nobody as zero rather than skipping it, which would flatter the average."),

    # ---- flow
    ("Joiners", "CALCULATE(COUNTROWS('Movement'), KEEPFILTERS('Movement'[Movement] = \"Joiner\"))",
     INT, None),
    ("Leavers", "CALCULATE(COUNTROWS('Movement'), KEEPFILTERS('Movement'[Movement] = \"Leaver\"))",
     INT, "People whose exit date falls in the period - including the 991 the HR system still\n"
     "calls Active."),
    ("Net Change", "[Joiners] - [Leavers]", "#,0;-#,0;0", None),
    ("Voluntary Leavers",
     "CALCULATE([Leavers], KEEPFILTERS('Employee'[Leaver Group] = \"Voluntary\"))", INT,
     "Voluntary and Resignation together - two source labels for one thing."),
    ("Voluntary Share %", "DIVIDE([Voluntary Leavers], [Leavers])", PCT, None),
    ("Early Leavers", "CALCULATE([Leavers], KEEPFILTERS('Employee'[Early Leaver] = \"Yes\"))",
     INT, "Leavers who went inside their first year."),
    ("Early Leaver Share %", "DIVIDE([Early Leavers], [Leavers])", PCT,
     "47% over the file: nearly half of everyone who leaves, leaves in year one. That is an\n"
     "onboarding and hiring question before it is a retention one."),
    ("Turnover Rate %", "DIVIDE([Leavers], [Average Headcount])", PCT,
     "Leavers over average headcount for the period in view, not annualised."),
    ("Annualised Turnover %",
     "DIVIDE([Leavers] * 12, [Average Headcount] * [Months in View])", PCT,
     "Turnover scaled to a year using the months actually in view, so 2023's seven months and\n"
     "2018's five compare with a full year."),
    ("Leavers 12M", f"CALCULATE([Leavers], {LAST_12M})", INT, None),
    ("Average Headcount 12M", f"CALCULATE([Average Headcount], {LAST_12M})", "#,0.0", None),
    ("Turnover 12M %", "DIVIDE([Leavers 12M], [Average Headcount 12M])", PCT,
     "Rolling twelve-month turnover at each month-end - the line to watch."),
    ("Median Tenure at Exit",
     "MEDIANX(\n"
     "    CALCULATETABLE(\n"
     "        SUMMARIZE('Movement', 'Employee'[Employee], 'Employee'[Tenure Years]),\n"
     "        KEEPFILTERS('Movement'[Movement] = \"Leaver\")\n"
     "    ),\n"
     "    'Employee'[Tenure Years]\n"
     ")", DEC2,
     "Years of service at the exit date, for leavers in the period. A median because a handful\n"
     "of long-service exits drag the mean."),

    # ---- engagement
    ("Surveys", f"CALCULATE(COUNTROWS('Engagement'), {IN_EMP.format(t='Engagement')})", INT,
     "Responses dated while the person was employed."),
    ("Surveys Outside Employment",
     f"CALCULATE(COUNTROWS('Engagement'), {OUT_EMP.format(t='Engagement')})", INT, None),
    ("Engagement Score",
     f"CALCULATE(AVERAGE('Engagement'[Engagement]), {IN_EMP.format(t='Engagement')})", DEC2,
     "Mean engagement, 1 to 5, from responses dated while the person was employed."),
    ("Engagement Score (all responses)", "AVERAGE('Engagement'[Engagement])", DEC2,
     "The same mean over every response, including the 1,338 from people who were not employed\n"
     "on the survey date. Kept to show the difference, which here is small - the problem is\n"
     "that the rows exist, not that they move the mean."),
    ("Satisfaction Score",
     f"CALCULATE(AVERAGE('Engagement'[Satisfaction]), {IN_EMP.format(t='Engagement')})", DEC2,
     None),
    ("Work-Life Balance Score",
     f"CALCULATE(AVERAGE('Engagement'[Work-Life Balance]), {IN_EMP.format(t='Engagement')})",
     DEC2, None),

    # ---- learning
    ("Training Records", f"CALCULATE(COUNTROWS('Training'), {IN_EMP.format(t='Training')})",
     INT, "Records dated while the person was employed."),
    ("Training Records Outside Employment",
     f"CALCULATE(COUNTROWS('Training'), {OUT_EMP.format(t='Training')})", INT, None),
    ("Training Cost", f"CALCULATE(SUM('Training'[Cost]), {IN_EMP.format(t='Training')})", USD,
     None),
    ("Training Cost (all records)", "SUM('Training'[Cost])", USD, None),
    ("Training Cost Outside Employment",
     f"CALCULATE(SUM('Training'[Cost]), {OUT_EMP.format(t='Training')})", USD,
     "Cost recorded against people who were not employed on the training date."),
    ("Unattributable Cost %",
     "DIVIDE([Training Cost Outside Employment], [Training Cost (all records)])", PCT, None),
    ("Training Days", f"CALCULATE(SUM('Training'[Days]), {IN_EMP.format(t='Training')})", INT,
     None),
    ("Completion Rate %",
     "DIVIDE(\n"
     "    CALCULATE([Training Records], KEEPFILTERS('Training'[Outcome] IN {\"Completed\", \"Passed\"})),\n"
     "    [Training Records]\n"
     ")", PCT, "Completed or passed, as a share of in-employment records."),
    ("Cost per Record", "DIVIDE([Training Cost], [Training Records])", USD, None),

    # ---- data quality
    ("Status Conflicts",
     "CALCULATE([Employees], KEEPFILTERS('Employee'[Status Check] = \"Contradicts dates\"))",
     INT, "People whose HR-system status disagrees with their own start and exit dates."),
    ("Status Conflict Rate %", "DIVIDE([Status Conflicts], [Employees])", PCT, None),

    # ---- labels
    ("Report Period",
     "VAR First = MIN('Date'[Date])\n"
     "VAR Last = MAX('Date'[Date])\n"
     "VAR WholeYears = MONTH(First) = 1 && DAY(First) = 1 && MONTH(Last) = 12 && DAY(Last) = 31\n"
     "RETURN\n"
     "    SWITCH(\n"
     "        TRUE(),\n"
     "        WholeYears && YEAR(First) = YEAR(Last), FORMAT(Last, \"yyyy\"),\n"
     "        FORMAT(First, \"mmm yyyy\") & \" to \" & FORMAT(Last, \"mmm yyyy\")\n"
     "    )", None,
     "A label for the period on screen: '2021', or 'Aug 2018 to Aug 2023'."),
]


def m_partition(name: str, file: str, spec: dict, local: bool) -> list[str]:
    if local:
        path = str((DATA / file).resolve()).replace("\\", "\\\\")
        src = f'File.Contents("{path}")'
    else:
        src = f'Web.Contents("{RAW}{file}")'
    n = len(spec["types"])
    types = ", ".join(f'{{"{c}", {t}}}' for c, t in spec["types"].items())
    lines = [
        f"\tpartition {q(name)} = m",
        "\t\tmode: import",
        "\t\tsource =",
        "\t\t\t\tlet",
        f'\t\t\t\t    Source = Csv.Document({src}, [Delimiter=",", Columns={n}, '
        f'Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
        '\t\t\t\t    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),',
    ]
    step = '#"Promoted Headers"'
    if spec.get("nullable"):
        # An empty CSV cell arrives as "", and "" does not convert to a date or a number - it
        # becomes a cell error. Make it null first so a blank exit date stays blank.
        cols = ", ".join(f'"{c}"' for c in spec["nullable"])
        lines.append(f'\t\t\t\t    #"Blanks to Null" = Table.ReplaceValue({step}, "", null, '
                     f'Replacer.ReplaceValue, {{{cols}}}),')
        step = '#"Blanks to Null"'
    lines += [
        f'\t\t\t\t    #"Applied Types" = Table.TransformColumnTypes({step}, {{{types}}})',
        "\t\t\t\tin",
        '\t\t\t\t    #"Applied Types"',
    ]
    return lines


def write_table(name: str, spec: dict, local: bool) -> None:
    lines: list[str] = []
    lines += doc(spec.get("doc"), 0)
    lines.append(f"table {q(name)}")
    lines.append(f"\tlineageTag: {tag('table', name)}")
    if spec.get("date_table"):
        lines.append("\tdataCategory: Time")
    for c in spec["columns"]:
        lines.append("")
        lines += doc(c.get("doc"), 1)
        lines.append(f"\tcolumn {q(c['name'])}")
        lines.append(f"\t\tdataType: {c['dtype']}")
        if c.get("hidden"):
            lines.append("\t\tisHidden")
        if c.get("key"):
            lines.append("\t\tisKey")
        if c.get("format"):
            lines.append(f"\t\tformatString: {c['format']}")
        lines.append(f"\t\tlineageTag: {tag('column', name, c['name'])}")
        lines.append("\t\tsummarizeBy: none")
        lines.append(f"\t\tsourceColumn: {c['source']}")
        if c.get("sortBy"):
            lines.append(f"\t\tsortByColumn: {q(c['sortBy'])}")
    if "files" in spec:
        for pname, f in zip(spec["partition_names"], spec["files"]):
            lines.append("")
            lines += m_partition(f"{name} {pname}", f, spec, local)
    else:
        lines.append("")
        lines += m_partition(name, spec["file"], spec, local)
    lines.append("")
    lines.append("\tannotation PBI_ResultType = Table")
    write(DEFN / "tables" / f"{name}.tmdl", lines)


def write_metrics() -> None:
    lines: list[str] = []
    lines += doc("Measure-only table. Nothing here stores data; the hidden column exists because\n"
                 "a table needs one. Every number on the report comes from here.", 0)
    lines.append("table Metrics")
    lines.append(f"\tlineageTag: {tag('table', 'Metrics')}")
    for name, dax, fmt, d in MEASURES:
        lines.append("")
        lines += doc(d, 1)
        body = dax.split("\n")
        if len(body) == 1:
            lines.append(f"\tmeasure {q(name)} = {body[0]}")
        else:
            lines.append(f"\tmeasure {q(name)} =")
            for b in body:
                lines.append(("\t\t\t" + b) if b.strip() else "\t\t\t")
        if fmt:
            lines.append(f"\t\tformatString: {fmt}")
        lines.append(f"\t\tlineageTag: {tag('measure', name)}")
    lines.append("")
    lines.append("\tcolumn Column")
    lines.append("\t\tdataType: string")
    lines.append("\t\tisHidden")
    lines.append(f"\t\tlineageTag: {tag('column', 'Metrics', 'Column')}")
    lines.append("\t\tsummarizeBy: none")
    lines.append("\t\tsourceColumn: Column")
    lines.append("")
    lines.append("\tpartition Metrics = m")
    lines.append("\t\tmode: import")
    lines.append("\t\tsource =")
    lines.append("\t\t\t\tlet")
    lines.append('\t\t\t\t    Source = #table(type table [Column = text], {})')
    lines.append("\t\t\t\tin")
    lines.append("\t\t\t\t    Source")
    lines.append("")
    lines.append("\tannotation PBI_ResultType = Table")
    write(DEFN / "tables" / "Metrics.tmdl", lines)


def write(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_json(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip("\n") + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true", help="read data/ from disk, not GitHub")
    args = ap.parse_args()

    if DEFN.exists():
        for attempt in range(5):
            try:
                shutil.rmtree(DEFN)
                break
            except PermissionError:
                if attempt == 4:
                    shutil.rmtree(DEFN, ignore_errors=True)
                else:
                    time.sleep(0.5)

    for name, spec in TABLES.items():
        write_table(name, spec, args.local)
    write_metrics()

    write(DEFN / "database.tmdl", ["database", "\tcompatibilityLevel: 1606"])

    order = ", ".join(f'"{t}"' for t in TABLES)
    write(DEFN / "model.tmdl", [
        "model Model",
        "\tculture: en-US",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tdiscourageImplicitMeasures",
        "\tsourceQueryCulture: en-US",
        "",
        f"annotation PBI_QueryOrder = [{order}]",
        "",
        "annotation __PBI_TimeIntelligenceEnabled = 0",
        "",
        'annotation PBI_ProTooling = ["DevMode"]',
        "",
    ] + [f"ref table {q(t)}" for t in list(TABLES) + ["Metrics"]])

    rel_lines: list[str] = []
    for i, (name, frm, to) in enumerate(RELATIONSHIPS):
        if i:
            rel_lines.append("")
        rel_lines += [f"relationship {q(name)}", f"\tfromColumn: {frm}", f"\ttoColumn: {to}"]
    write(DEFN / "relationships.tmdl", rel_lines)

    write_json(MODEL / "definition.pbism", """
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
  "version": "4.2",
  "settings": {
    "qnaEnabled": true
  }
}""")
    write_json(MODEL / ".platform", f"""
{{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
  "metadata": {{
    "type": "SemanticModel",
    "displayName": "Workforce Analytics"
  }},
  "config": {{
    "version": "2.0",
    "logicalId": "{tag('platform', 'model')}"
  }}
}}""")

    n_cols = sum(len(s["columns"]) for s in TABLES.values())
    print(f"{len(TABLES) + 1} tables, {n_cols} columns, {len(MEASURES)} measures, "
          f"{len(RELATIONSHIPS)} relationships -> {MODEL.name} "
          f"({'local files' if args.local else 'GitHub raw'})")


if __name__ == "__main__":
    main()
