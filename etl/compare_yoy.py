"""Diff etl/verify_yoy.ps1 output (the live model) against etl/yoy_expected.py (pandas).

    powershell -File etl/verify_yoy.ps1 -Year 2023 -Comparison "Prior year" > dax.txt
    python etl/compare_yoy.py dax.txt 2023 prior [NEL]

Checks the headline, every month of all three chart metrics, every department, both Top and
Bottom division tables in order, and the headline again with the panel's Business Unit pinned.
Exit code 1 on any mismatch.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sections(text: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    name, header = None, None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("== "):
            name, header = line[3:], None
            out[name] = []
        elif name and line and not line.startswith("("):
            cells = [c.strip() for c in line.split(" | ")]
            if header is None:
                header = [c.split("[")[-1].rstrip("]") for c in cells]
            else:
                out[name].append(dict(zip(header, cells)))
    return out


def num(v: str) -> float:
    return float(v) if v not in ("", None) else 0.0


class Check:
    def __init__(self):
        self.n, self.bad = 0, []

    def eq(self, label: str, dax, expected, tol: float = 1e-3):
        self.n += 1
        if isinstance(expected, str):
            ok = str(dax) == expected
        else:
            ok = abs(num(dax) - float(expected or 0)) <= tol
        if not ok:
            self.bad.append(f"{label}: model {dax!r}, pandas {expected!r}")


def expected(year: int, comp: str, unit: str | None) -> dict:
    args = [sys.executable, str(ROOT / "etl" / "yoy_expected.py"), str(year), comp]
    if unit:
        args.append(f"Business Unit={unit}")
    return json.loads(subprocess.run(args, check=True, capture_output=True, text=True).stdout)


def headline(c: Check, prefix: str, row: dict, e: dict) -> None:
    c.eq(f"{prefix} available", row["Available"], "True" if e["available"] else "False")
    a = e["actual"]
    for key, col in [("headcount", "Headcount"), ("avg", "Avg"), ("joiners", "Joiners"), ("leavers", "Leavers"),
                     ("early_share", "Early share"), ("turnover", "Turnover")]:
        c.eq(f"{prefix} {col}", row[col], a[key])
    if e["available"]:
        b = e["comparison"]
        for key, col in [("headcount", "Headcount comp"), ("avg", "Avg comp"), ("joiners", "Joiners comp"),
                         ("leavers", "Leavers comp"), ("early_share", "Early share comp"), ("turnover", "Turnover comp")]:
            c.eq(f"{prefix} {col}", row[col], b[key])
        c.eq(f"{prefix} depts up", row["Depts up"], e["departments_up"])
        c.eq(f"{prefix} depts", row["Depts"], len(e["departments"]))
        c.eq(f"{prefix} divisions up", row["Divisions up"], e["divisions_up"])
        c.eq(f"{prefix} divisions", row["Divisions"], e["divisions_in_play"])
    else:
        for col in ["Headcount comp", "Leavers comp", "Turnover comp", "Depts up", "Divisions"]:
            c.eq(f"{prefix} {col} blank", row.get(col, ""), "")  # trailing blank cells are trimmed


def main() -> None:
    text = Path(sys.argv[1]).read_text(encoding="utf-8-sig")
    year, comp = int(sys.argv[2]), sys.argv[3]
    unit = sys.argv[4] if len(sys.argv) > 4 else "NEL"
    s = sections(text)
    e = expected(year, comp, None)
    c = Check()

    head = next(k for k in s if k.startswith("Headline"))
    headline(c, "headline", s[head][0], e)

    if e["available"]:
        for metric in ["headcount", "joiners", "leavers"]:
            rows = {int(r["Month No"]): r for r in s[f"Monthly {metric.capitalize()}"] if r["This"]}
            c.eq(f"{metric} months", len(rows), len(e["monthly"]))
            for m in e["monthly"]:
                r = rows.get(m["month"], {})
                c.eq(f"{metric} m{m['month']} this", r.get("This"), m[metric])
                c.eq(f"{metric} m{m['month']} comparison", r.get("Comparison"), m[f"{metric}_comp"])
                c.eq(f"{metric} m{m['month']} change", r.get("Change"), m[metric] - m[f"{metric}_comp"])

        depts = {r["Department"]: r for r in s["Departments"]}
        c.eq("department rows", len(depts), len(e["departments"]))
        for d in e["departments"]:
            r = depts.get(d["name"], {})
            c.eq(f"dept {d['name']} headcount", r.get("Headcount"), d["headcount"])
            c.eq(f"dept {d['name']} leavers", r.get("Leavers"), d["leavers"])
            c.eq(f"dept {d['name']} was", r.get("Was"), d["leavers_comp"])
            c.eq(f"dept {d['name']} turnover", r.get("Turnover"), d["turnover"])
            c.eq(f"dept {d['name']} turnover was", r.get("Turnover was"), d["turnover_comp"])
            c.eq(f"dept {d['name']} change pp", r.get("Change pp"), round(d["change_pp"], 1), tol=0.051)

        for show, key in [("Top", "divisions_top"), ("Bottom", "divisions_bottom")]:
            rows = s[f"Divisions, {show} 8"]
            c.eq(f"{show} row count", len(rows), len(e[key]))
            for i, d in enumerate(e[key]):
                r = rows[i] if i < len(rows) else {}
                c.eq(f"{show} #{i + 1} name", r.get("Division"), d["name"])
                c.eq(f"{show} #{i + 1} rank", r.get("Rank"), i + 1)
                c.eq(f"{show} #{i + 1} leavers", r.get("Leavers"), d["leavers"])
                c.eq(f"{show} #{i + 1} was", r.get("Was"), d["leavers_comp"])
                c.eq(f"{show} #{i + 1} change", r.get("Change"), d["change"])

        eu = expected(year, comp, unit)
        panel = s[next(k for k in s if k.startswith("Panel slicer pinned: Business Unit"))][0]
        headline(c, f"panel {unit}", panel, eu)
        c.eq(f"panel {unit} summary", panel["Filter summary"], "Filtered by business unit")
        pdepts = {r["Department"]: r for r in s[next(k for k in s if k.startswith("Panel slicer pinned: departments"))]}
        for d in eu["departments"]:
            r = pdepts.get(d["name"], {})
            c.eq(f"panel dept {d['name']} leavers", r.get("Leavers"), d["leavers"])
            c.eq(f"panel dept {d['name']} change pp", r.get("Change pp"), round(d["change_pp"], 1), tol=0.051)
    else:
        for show in ["Top", "Bottom"]:
            c.eq(f"{show} rows when empty", len(s[f"Divisions, {show} 8"]), 0)
        c.eq("department rows when empty", len(s["Departments"]), 0)
        for metric in ["Headcount", "Joiners", "Leavers"]:
            c.eq(f"{metric} chart points when empty", len([r for r in s[f"Monthly {metric}"] if r.get("This")]), 0)

    print(f"{year} {comp}: {c.n - len(c.bad)} of {c.n} checks match")
    for b in c.bad:
        print("  MISMATCH", b)
    sys.exit(1 if c.bad else 0)


if __name__ == "__main__":
    main()
