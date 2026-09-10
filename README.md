# Workforce analytics - a Power BI model you can review

Five years of an organisation's HR records - 3,000 people, August 2018 to August 2023 - rebuilt
as a Power BI star schema: headcount, joiners and leavers, turnover, engagement and training.

The whole project is text. The semantic model is TMDL, the report is PBIR, and both are generated
by the Python in `etl/`, so every measure, relationship and visual can be read and diffed in a
pull request.

![Overview](screenshots/overview.png)

## What it finds

- **Turnover rose every year** - 6.7% annualised in 2018, 19.2% in 2021, 27.4% in 2022 and 62.8%
  over the first seven months of 2023. Headcount peaked at 1,728 in December 2022 and was 1,480
  by July 2023.
- **Nearly half of leavers go in their first year** - 725 of 1,533 (47%). The median leaver had
  served 1.07 years.
- **$735,145 of training cost - 44% of the total - is recorded against people who were not
  employed on the training date.**

## What the source gets wrong, and what the model does about it

| Problem | Evidence | Decision |
|---|---|---|
| The HR system's status contradicts the dates | 991 "Active" people have a past exit date; all 69 "Future Start" and all 86 "Leave of Absence" have exit dates too - 1,146 in all | Employed or left is derived from start and exit dates. The source label is kept as `Source Status`, with a `Status Check` flag |
| The recruitment file is not this company's | IDs 1001-4000 collide with employee IDs; 0 of 3,000 names match on a shared ID; no applicant's job title exists in the company; every applicant pairs a US state with a non-US country | Tested in the ETL, recorded in `data/quality_report.json`, left out of the model |
| Surveys and training dated outside employment | 1,338 surveys and 1,317 training records fall before the start or after the exit date | Every row carries `In Employment`; headline measures use in-employment rows, naive figures sit beside them |
| Trailing spaces | All 2,020 Production rows in `DepartmentType` | Trimmed |
| Two date formats | `dd-Mon-yy` for most fields, `dd-mm-yyyy` for birth and survey dates - proven day-first (first component > 12 in 1,823 rows, second never) | Parsed explicitly per column |
| Overlapping termination types | "Voluntary" and "Resignation" are the same thing | Kept as `Leaver Reason`, merged in `Leaver Group` |
| Personal data | Names, emails, supervisor names, dates of birth | Dropped in the ETL. Age survives as a band, supervisor as an opaque key |

The data is synthetic and shows it: the four termination reasons arrive in near-identical numbers
(388, 388, 380, 377). The report shows the split and builds nothing on it.

## Model

| Table | Grain | Rows |
|---|---|---|
| `Employee` | one per person | 3,000 |
| `Date` | one per day, marked date table | 1,857 |
| `Program` | training programme | 5 |
| `Headcount` | employee x month-end employed | 68,587 |
| `Movement` | joiner or leaver event | 4,533 |
| `Engagement` | survey response | 3,000 |
| `Training` | training record | 3,000 |

Headcount is a stock: `[Headcount]` reads the last month-end in view and `[Average Headcount]`
averages month-ends, so nothing ever sums it across time. Turnover is annualised over the months
actually present - 2018 holds five and 2023 seven.

## Build

```
python etl/build_star_schema.py      # data/ and data/quality_report.json from data/source/
python etl/build_model.py            # TMDL - partitions read data/ from this repo on GitHub
python etl/build_report.py           # PBIR
powershell -File etl/check_tmdl.ps1  # parse the TMDL with Desktop's own serializer
```

Open `Workforce Analytics.pbip` in Power BI Desktop and refresh. `etl/verify_measures.py`
recomputes ten measures in pandas by year, by department and in total and diffs them against
the live model - 130 checks, all passing.

## Source and licence

[Employee/HR Dataset (All in One)](https://www.kaggle.com/datasets/ravindrasinghrana/employeedataset)
on Kaggle, released CC0 1.0. The source CSVs are committed under `data/source/`. Code: see
`LICENSE`.

Built by [Milestone BI](https://milestonebi.com/workforce-analytics/).
