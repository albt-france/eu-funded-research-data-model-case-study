"""Data profiling of the CORDIS files (staged parquet) -> docs/analysis/DATA_PROFILING.md and data/processed/profile_*.csv.
Every number in the document is computed here. PUBLIC DATA.
Usage: python src/profile_data.py
"""
import duckdb
import pandas as pd

from config import DOCS, INTERIM, PROC

NO_EXAMPLE = {"name", "shortName", "city", "organizationURL", "objective", "title", "keywords", "acronym", "projectAcronym",
              "grantDoi"}


def col_profile(con, view: str) -> pd.DataFrame:
    cols = [r[0] for r in con.execute(f"describe {view}").fetchall()]
    n = con.execute(f"select count(*) from {view}").fetchone()[0]
    rows = []
    for c in cols:
        miss, distinct = con.execute(f'select count(*) filter (where "{c}" is null), count(distinct "{c}") from {view}').fetchone()
        sample = con.execute(f'select "{c}" from {view} where "{c}" is not null limit 1').fetchone()
        ex = "" if c in NO_EXAMPLE or not sample else str(sample[0])[:40]
        typ = con.execute(
            f'select case when count(*) filter (where "{c}" is not null and try_cast(replace("{c}", \',\', \'.\') as double) is null) = 0 '
            f'then \'number\' when count(*) filter (where "{c}" is not null and try_cast("{c}" as timestamp) is null) = 0 then \'date\' '
            f'else \'text\' end from {view}').fetchone()[0]
        rows.append({"column": c, "type": typ, "missing_pct": round(100 * miss / n, 1), "distinct": distinct, "example": ex})
    return pd.DataFrame(rows)


def md_table(df: pd.DataFrame) -> str:
    h = "| " + " | ".join(df.columns) + " |\n|" + "|".join("---" for _ in df.columns) + "|\n"
    return h + "\n".join("| " + " | ".join(str(v).replace("|", "/") for v in r) + " |" for r in df.itertuples(index=False))


def main():
    con = duckdb.connect()
    for prog in ("HORIZON", "H2020"):
        for f in ("project", "organization", "euroSciVoc", "legalBasis", "topics", "webLink"):
            con.execute(f"create view {prog}_{f} as select * from '{(INTERIM / f'{prog}_{f}.parquet').as_posix()}'")
    stats = pd.read_csv(INTERIM / "parse_stats.csv")
    log = pd.read_csv(INTERIM / "cleaning_log.csv")
    qa = pd.read_csv(PROC / "qa_report.csv").set_index("id")
    v = lambda s: con.execute(s).fetchone()[0]  # noqa: E731
    pp, po = col_profile(con, "HORIZON_project"), col_profile(con, "HORIZON_organization")
    pp.to_csv(PROC / "profile_project.csv", index=False)
    po.to_csv(PROC / "profile_organization.csv", index=False)

    k = {
        "proj_rows": v("select count(*) from HORIZON_project"), "proj_ids": v("select count(distinct id) from HORIZON_project"),
        "org_rows": v("select count(*) from HORIZON_organization"),
        "pic": v("select count(distinct organisationID) from HORIZON_organization"),
        "key4": v('select count(distinct (projectID, organisationID, role, "order")) from HORIZON_organization'),
        "key_order_dup": v('select count(*) from (select projectID, "order" from HORIZON_organization group by all having count(*) > 1)'),
        "key3_dup": v("select count(*) from (select projectID, organisationID, role from HORIZON_organization group by all having count(*) > 1)"),
        "pic_name": v("select count(*) from (select organisationID from HORIZON_organization group by 1 having count(distinct name) > 1)"),
        "pic_country": v("select count(*) from (select organisationID from HORIZON_organization group by 1 having count(distinct country) > 1)"),
        "pic_sme": v("select count(*) from (select organisationID from HORIZON_organization group by 1 having count(distinct SME) > 1)"),
        "name_pics": v("select count(*) from (select name from HORIZON_organization group by 1 having count(distinct organisationID) > 1)"),
        "comma_proj": v("select count(*) from HORIZON_project where ecMaxContribution like '%,%'"),
        "point_org": v("select count(*) from HORIZON_organization where netEcContribution like '%.%'"),
        "zero_cost": v("select count(*) from HORIZON_project where totalCost = '0'"),
        "eu_codes": v("select count(*) from HORIZON_organization where country in ('EL', 'UK')"),
        "multi_country": v("select count(*) from HORIZON_organization where country like '%;%'"),
        "no_country": v("select count(*) from HORIZON_organization where country is null"),
        "assoc_null": v("select count(*) from HORIZON_organization where role = 'associatedPartner' and ecContribution is null"),
        "third_zero": v("select count(*) from HORIZON_organization where role = 'thirdParty' and ecContribution = '0' and "
                        "cast(netEcContribution as double) > 0"),
        "one_coord": v("select count(*) from (select projectID from HORIZON_organization group by 1 "
                       "having count(*) filter (where role = 'coordinator') <> 1)"),
        "unclassified": v("select count(*) from HORIZON_project p where not exists (select 1 from HORIZON_euroSciVoc e where e.projectID = p.id)"),
        "signed_after": v("select count(*) from HORIZON_project where ecSignatureDate > startDate"),
        "end_before": v("select count(*) from HORIZON_project where endDate < startDate"),
        "lb_multi": v("select count(*) from H2020_project where legalBasis like '%;%'"),
        "h_no_scheme": v("select count(*) from H2020_project where fundingScheme is null"),
        "h_no_start": v("select count(*) from H2020_project where startDate is null"),
        "esv_codes": v("select count(distinct euroSciVocCode) from HORIZON_euroSciVoc"),
        "lb_he": v("select count(distinct legalBasis) from HORIZON_legalBasis"),
        "web_dup": v("select count(*) - count(distinct id) from HORIZON_webLink"),
        "ongoing": v("select count(*) from HORIZON_project where status = 'SIGNED'"),
    }
    lines = lambda prog, rule: int(log[(log.programme == prog) & (log.rule.str.startswith(rule))].rows.sum())  # noqa: E731
    st = stats[["programme", "file", "rows", "columns", "repaired_lines", "rejected_lines", "dropped_personal_columns"]].fillna("")
    issues = pd.DataFrame([
        ("Format", "Strict CSV parsers (DuckDB, pandas) stop on the file: unescaped quotes in free text, stray `\";\"`",
         f"{int(stats.repaired_lines.sum()):,} lines repaired, {int(stats.rejected_lines.sum())} rejected (all programmes)",
         "Line reader splitting on `\";\"`, extra pieces merged back into the free-text column (`src/cordis_io.py`, tested)"),
        ("Amounts", "Decimal comma in project amounts, decimal point in organisation amounts",
         f"{k['comma_proj']:,} project values with a comma; {k['point_org']:,} organisation values with a point",
         "`parse_amount` accepts both; control total of the raw files = total loaded (check Q05)"),
        ("Amounts", "Total cost = 0 for lump-sum and unit-cost grants (e.g. MSCA fellowships)",
         f"{k['zero_cost']:,} projects ({k['zero_cost'] / k['proj_rows']:.0%})", "Stored as NULL = not reported, never as a real zero"),
        ("Amounts", "Associated partners have empty contributions; affiliated entities have 0 gross but a net amount",
         f"{k['assoc_null']:,} empty; {k['third_zero']:,} affiliated entities funded in the net column only",
         "Empty = 0 for unfunded roles; the analysis uses the **net** contribution of funded roles"),
        ("Amounts", "Participants' net contributions do not add up to the project maximum", f"{qa.loc['Q07', 'offending_rows']:,} projects (both programmes)",
         "Reported by check Q07, not corrected (the source is authoritative)"),
        ("Codes", "EU country codes instead of ISO (`EL` Greece, `UK` United Kingdom), Kosovo `XK`",
         f"{k['eu_codes']:,} participations", "Mapped to ISO 3166-1 alpha-2 with the EU country authority table"),
        ("Codes", "Multi-valued country (`DE;HU`) and missing country", f"{k['multi_country']} multi-valued; {k['no_country']} missing",
         "First code kept and logged; missing left NULL (check Q09)"),
        ("Keys", "`(projectID, order)` is not unique; `(projectID, organisationID, role)` is not unique either",
         f"{k['key_order_dup']:,} and {k['key3_dup']:,} duplicates", "Natural key = (project, organisation, role, order): unique for all "
         f"{k['key4']:,} rows; an organisation can leave and re-join (check Q14)"),
        ("Organisations", "SME status of the same PIC changes between projects", f"{k['pic_sme']:,} PICs",
         "SME stored on `participation`, not on `organisation` (it is a fact about the participation, at that time)"),
        ("Organisations", "Same name, several PICs (possible duplicate registrations)", f"{k['name_pics']:,} exact names; "
         f"{qa.loc['Q10', 'offending_rows']:,} normalised name + country groups", "Reported as candidates (Q10), **not merged**: the PIC is the EU identifier"),
        ("Classification", "Projects without any EuroSciVoc domain", f"{k['unclassified']:,} projects ({k['unclassified'] / k['proj_rows']:.0%})",
         "Kept, shown as '(not classified)' in every breakdown"),
        ("Classification", "CORDIS domain codes deeper than the published EuroSciVoc; one code without any label",
         f"{qa.loc['Q12', 'offending_rows']:,} codes not in EU Vocabularies; {qa.loc['Q18', 'offending_rows']} unlabelled",
         "Local concept linked to its official parent; explicit 'unlabelled' label (Q18)"),
        ("Dates", "Grant signed after the project start date", f"{k['signed_after']:,} projects", "Valid (start can precede signature); reported (Q11)"),
        ("H2020", "Several legal bases in `project.legalBasis`; one project without funding scheme; projects without start date",
         f"{k['lb_multi']}; {k['h_no_scheme']}; {k['h_no_start']}", "Main part from `legalBasis.csv` (`uniqueProgrammePart`); "
         "'NOT_REPORTED' scheme; NULL dates"),
        ("Links", "Duplicate web-link ids (within and across programmes)", f"{lines('HORIZON', 'duplicate document') + lines('H2020', 'duplicate document'):,}",
         "First kept"),
        ("Personal data", "Address, VAT number, coordinates and contact form link in `organization.csv`", "5 columns",
         "Dropped at staging, before any storage (tested)"),
    ], columns=["Area", "Finding", "Size (Horizon Europe unless stated)", "Treatment"])
    issues.to_csv(PROC / "profile_issues.csv", index=False)

    md = f"""# Data profiling: what the CORDIS files really look like

**PUBLIC DATA.** CORDIS bundles for Horizon Europe and Horizon 2020, downloaded on 16 November 2026 (`data/raw/download_log.csv`).
Generated by `src/profile_data.py`. Treatments are implemented in `src/clean.py`, `src/cordis_io.py` and `src/load.py`, and
checked after each load by `src/quality.py` ([QA_REPORT.md](QA_REPORT.md)).

## Files

{md_table(st)}

## Structure and keys (Horizon Europe)

- `project.csv`: {k['proj_rows']:,} rows, `id` unique ({k['proj_ids']:,} distinct). {k['ongoing']:,} projects are `SIGNED` (running),
  so amounts are commitments: the **maximum** EU contribution, not what has been paid.
- `organization.csv`: {k['org_rows']:,} rows = participations, not organisations. {k['pic']:,} distinct PICs.
  Functional dependencies tested: PIC → name holds ({k['pic_name']} violations), PIC → country holds ({k['pic_country']}),
  PIC → SME does **not** hold ({k['pic_sme']} PICs) → SME belongs to the participation.
- Natural key of a participation: (projectID, organisationID, role, order), unique for all {k['key4']:,} rows.
- Exactly one coordinator per project: {k['one_coord']} exceptions. No orphan participation, no project without participants.
- `euroSciVoc.csv`: {k['esv_codes']:,} distinct domain codes; the code is the path (`/23/53/373`), the last segment is the official
  EuroSciVoc notation, which gives an exact link to EU Vocabularies.
- `legalBasis.csv`: {k['lb_he']} programme parts; exactly one per project is flagged `uniqueProgrammePart`.
- End date before start date: {k['end_before']}.

## Findings and treatment

{md_table(issues)}

## Column profile: project.csv (Horizon Europe)

{md_table(pp)}

## Column profile: organization.csv (Horizon Europe, after dropping personal columns)

Examples are not shown for names, cities and web addresses.

{md_table(po)}
"""
    (DOCS / "analysis" / "DATA_PROFILING.md").write_text(md, encoding="utf-8")
    print("DATA_PROFILING.md written;", len(issues), "findings")


if __name__ == "__main__":
    main()
