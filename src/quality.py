"""Automatic quality checks after each load. Each check is one SQL query that counts the rows breaking a rule.
FAIL = the load must be fixed; WARN = a known property of the source, reported and explained; PASS = 0 rows.
Output: data/processed/qa_report.csv and docs/analysis/QA_REPORT.md
"""
from pathlib import Path

import duckdb
import pandas as pd

from config import DOCS, PROC

CHECKS = [  # id, rule, severity if > 0, SQL returning the number of offending rows
    ("Q01", "Every project has exactly one coordinator", "FAIL",
     "select count(*) from (select p.project_id, count(x.participation_id) filter (where x.role_code = 'coordinator') k "
     "from project p left join participation x using (project_id) group by 1) where k <> 1"),
    ("Q02", "Every project has at least one participation", "FAIL",
     "select count(*) from project p where not exists (select 1 from participation x where x.project_id = p.project_id)"),
    ("Q03", "Raw rows = loaded rows (projects)", "FAIL",
     "select abs((select sum(rows_read) from load_batch) * 0 + (select count(*) from project) - {raw_projects})"),
    ("Q04", "Raw rows = loaded rows (participations)", "FAIL",
     "select abs((select count(*) from participation) - {raw_participations})"),
    ("Q05", "Control total: EU contribution loaded = EU contribution in the raw files (EUR, rounded)", "FAIL",
     "select abs(round((select sum(ec_max_contribution) from project) - {raw_ec_total}))"),
    ("Q06", "Unfunded roles (associated partners) carry no EU contribution in the source (kept, excluded from the measure)", "WARN",
     "select count(*) from participation x join participant_role r using (role_code) "
     "where not r.receives_eu_funding and coalesce(x.net_ec_contribution, 0) > 0"),
    ("Q07", "Sum of participants' net contributions = project maximum contribution (1 EUR tolerance)", "WARN",
     "select count(*) from (select p.project_id, p.ec_max_contribution m, sum(coalesce(x.net_ec_contribution, 0)) s "
     "from project p join participation x using (project_id) join participant_role r using (role_code) "
     "where r.receives_eu_funding group by all) where abs(m - s) > 1"),
    ("Q08", "Projects without a EuroSciVoc classification", "WARN",
     "select count(*) from project p where not exists (select 1 from project_science_domain d where d.project_id = p.project_id)"),
    ("Q09", "Participations without a country", "WARN",
     "select count(*) from participation x join organisation o using (organisation_id) where o.country_code is null"),
    ("Q10", "Duplicate organisation candidates (same normalised name and country, different PIC)", "WARN",
     "select count(*) from (select name_key, country_code from organisation where name_key is not null "
     "group by all having count(*) > 1)"),
    ("Q11", "Grant signed after the project start date", "WARN",
     "select count(*) from project where signature_date > start_date"),
    ("Q12", "CORDIS domain codes not found in the official EuroSciVoc (EU Vocabularies)", "WARN",
     "select count(*) from science_domain where euroscivoc_uri is null"),
    ("Q18", "Domain codes used by CORDIS without any label (path and title empty in the source)", "WARN",
     "select count(*) from science_domain where label like 'unlabelled CORDIS concept%'"),
    ("Q13", "Project total cost not reported (lump sum or unit cost grants)", "WARN",
     "select count(*) from project where total_cost is null"),
    ("Q14", "Organisation leaves and re-joins a project in the same role (two rows, different order)", "WARN",
     "select count(*) from (select project_id, organisation_id, role_code from participation group by all having count(*) > 1)"),
    ("Q15", "Reporting periods loaded (not published in CORDIS open data)", "WARN",
     "select case when (select count(*) from reporting_period) = 0 then 1 else 0 end"),
    ("Q16", "Star schema: fact total = model total (EUR, rounded)", "FAIL",
     "select abs(round((select sum(net_ec_contribution) from mart.fact_participation) - "
     "(select sum(coalesce(x.net_ec_contribution, 0)) from participation x join participant_role r using (role_code) "
     "where r.receives_eu_funding)))"),
    ("Q17", "Domain bridge weights add up to 1 per classified project", "FAIL",
     "select count(*) from (select project_id, sum(weight) w from mart.bridge_project_domain group by 1) where abs(w - 1) > 1e-9"),
]


def raw_controls(base: Path) -> dict:
    """Control totals computed directly on the staged raw files, independently of the load code."""
    con = duckdb.connect()
    out = {"raw_projects": 0, "raw_participations": 0, "raw_ec_total": 0.0}
    for f in sorted(base.glob("*_project.parquet")):
        out["raw_projects"] += con.execute(f"select count(*) from '{f.as_posix()}'").fetchone()[0]
        out["raw_ec_total"] += con.execute(
            f"select coalesce(sum(cast(replace(ecMaxContribution, ',', '.') as double)), 0) from '{f.as_posix()}'").fetchone()[0]
    for f in sorted(base.glob("*_organization.parquet")):
        out["raw_participations"] += con.execute(f"select count(*) from '{f.as_posix()}'").fetchone()[0]
    return out


def run_checks(db: Path, base: Path, write: bool = True) -> pd.DataFrame:
    ctrl = raw_controls(base)
    con = duckdb.connect(str(db), read_only=True)
    rows = []
    for cid, rule, sev, sql in CHECKS:
        n = con.execute(sql.format(**ctrl)).fetchone()[0]
        rows.append({"id": cid, "rule": rule, "offending_rows": int(n or 0), "status": "PASS" if not n else sev})
    con.close()
    qa = pd.DataFrame(rows)
    if write and base.resolve() == (PROC.parent / "interim").resolve():
        PROC.mkdir(parents=True, exist_ok=True)
        qa.to_csv(PROC / "qa_report.csv", index=False)
        log = pd.read_csv(base / "cleaning_log.csv") if (base / "cleaning_log.csv").exists() else pd.DataFrame()
        md = ["# Quality report (generated by src/quality.py after each load)", "",
              "FAIL = the load must be fixed. WARN = a known property of the source, reported and explained in "
              "[DATA_PROFILING.md](DATA_PROFILING.md). PASS = no offending row.", "",
              "| Id | Rule | Offending rows | Status |", "|---|---|---:|---|"]
        md += [f"| {r.id} | {r.rule} | {r.offending_rows:,} | {r.status} |" for r in qa.itertuples()]
        if len(log):
            md += ["", "## Cleaning rules applied", "", "| Programme | Rule | Rows |", "|---|---|---:|"]
            md += [f"| {r.programme} | {r.rule} | {r.rows:,} |" for r in log.itertuples()]
        md += ["", f"Control totals from the raw files: {ctrl['raw_projects']:,} projects, {ctrl['raw_participations']:,} "
               f"participations, EUR {ctrl['raw_ec_total']:,.0f} maximum EU contribution."]
        (DOCS / "analysis").mkdir(parents=True, exist_ok=True)
        (DOCS / "analysis" / "QA_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return qa


if __name__ == "__main__":
    from config import DB, INTERIM
    print(run_checks(DB, INTERIM).to_string(index=False))
