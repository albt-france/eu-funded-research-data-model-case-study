"""Load: staged CORDIS files -> cleaned, normalised tables -> DuckDB database (model/ddl/schema.sql), then quality checks.

Usage: python src/load.py [--interim data/interim] [--db data/cordis.duckdb] [--skip-stage]
Steps: stage raw files (robust parsing, personal columns dropped) -> build reference tables -> build programme tables
-> insert in foreign-key order (hierarchies parent level first) -> create the analytical mart -> run quality checks.
"""
import datetime as dt
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from clean import (country_iso2, domain_parent, normalise_name, parse_amount, parse_date, programme_part_parent,
                   to_bool)
from config import DB, DDL, EU27, INTERIM, MART, ORG_TYPES, PROGRAMMES, RAW, REF
from stage import read, stage

ROLES = [  # role_code, group, receives EU funding, label
    ("coordinator", "coordinator", True, "Coordinator: beneficiary that signs for and represents the consortium"),
    ("participant", "beneficiary", True, "Beneficiary (Horizon Europe and H2020 'participant')"),
    ("thirdParty", "affiliated entity", True, "Affiliated entity / linked third party, funded through its beneficiary"),
    ("associatedPartner", "associated partner", False, "Associated partner (Horizon Europe): takes part without EU funding"),
    ("partner", "associated partner", False, "Partner organisation (H2020): takes part without EU funding"),
    ("internationalPartner", "associated partner", False, "International partner (H2020): third-country partner without EU funding"),
]
EXTRA_PARENTS = {"EURATOM.1": "EURATOM2027"}


def action_family(code: str) -> str:
    """Funding scheme code -> family of the type of action (e.g. 'HORIZON-JU-RIA' -> research and innovation action)."""
    c = (code or "").upper()
    tokens = set(c.split("-"))
    for key, fam in (("ERC", "ERC frontier research"), ("MSCA", "Marie Sklodowska-Curie"), ("EIC", "EIC innovation"),
                     ("COFUND", "Co-fund")):
        if key in c:
            return fam
    if "SME" in tokens:
        return "SME instrument"
    for key, fam in (("CSA", "Coordination and support action"), ("RIA", "Research and innovation action"),
                     ("IA", "Innovation action")):
        if key in tokens:
            return fam
    return "Other"


# ------------------------------------------------------------------------------------------------- reference
def reference_tables(used_countries: set[str]) -> dict[str, pd.DataFrame]:
    fp = pd.DataFrame([{"programme_code": k, "name": v["name"], "start_year": v["start"], "end_year": v["end"],
                        "legal_act": v["legal_act"], "legal_act_url": v["url"]} for k, v in PROGRAMMES.items()])
    c = pd.read_csv(REF / "countries.csv", dtype=str, keep_default_na=False)
    c = c[c.alpha2 != ""].sort_values("country").drop_duplicates("alpha2")
    country = pd.DataFrame({"country_code": c.alpha2, "iso3_code": c.alpha3, "eu_code": c.eu_code.replace("", None),
                            "name": c.label, "is_eu27": c.alpha2.isin(EU27), "authority_uri": c.country})
    missing = sorted(used_countries - set(country.country_code))
    if missing:
        country = pd.concat([country, pd.DataFrame({"country_code": missing, "iso3_code": None, "eu_code": None,
                                                    "name": missing, "is_eu27": False, "authority_uri": None})])
    org_type = pd.DataFrame(list(ORG_TYPES.items()), columns=["type_code", "label"])
    roles = pd.DataFrame(ROLES, columns=["role_code", "role_group", "receives_eu_funding", "label"])
    return {"framework_programme": fp, "country": country, "organisation_type": org_type, "participant_role": roles}


# ------------------------------------------------------------------------------------------------- per programme
def build_programme(prog: str, base: Path, log: list) -> dict[str, pd.DataFrame]:
    p, o = read(prog, "project", base), read(prog, "organization", base)
    lb, esv = read(prog, "legalBasis", base), read(prog, "euroSciVoc", base)
    tp, wl = read(prog, "topics", base), read(prog, "webLink", base)

    # programme parts: codes used + pillar rows from the legal acts, parent = nearest existing ancestor
    pil = pd.read_csv(REF / "programme_pillars.csv")
    pil = pil[pil.programme_code == prog]
    parts = (lb.groupby("legalBasis").title.first().reset_index().rename(columns={"legalBasis": "part_code"}))
    parts = pd.concat([pil[["part_code", "title"]], parts[~parts.part_code.isin(pil.part_code)]], ignore_index=True)
    known = set(parts.part_code)

    def parent(code):
        if code in EXTRA_PARENTS:
            return EXTRA_PARENTS[code]
        cur = programme_part_parent(code)
        while cur and cur not in known:
            cur = programme_part_parent(cur)
        return cur
    parts["parent_part_code"] = parts.part_code.map(parent)
    depth = {}

    def d(code):
        if code not in depth:
            par = parts.set_index("part_code").parent_part_code.get(code)
            depth[code] = 1 if not isinstance(par, str) else d(par) + 1
        return depth[code]
    parts["depth"] = parts.part_code.map(d)
    parts["programme_code"] = prog

    # project
    proj = pd.DataFrame({
        "project_id": p.id.astype("int64"), "acronym": p.acronym.fillna(p.id), "title": p.title.fillna(p.acronym),
        "status": p.status, "programme_code": prog, "main_part_code": p.legalBasis, "call_code": p.masterCall,
        "topic_code": p.topics, "scheme_code": p.fundingScheme,
        "signature_date": p.ecSignatureDate.map(parse_date), "start_date": p.startDate.map(parse_date),
        "end_date": p.endDate.map(parse_date), "total_cost": p.totalCost.map(parse_amount),
        "ec_max_contribution": p.ecMaxContribution.map(parse_amount), "grant_doi": p.grantDoi, "keywords": p.keywords,
        "objective": p.objective, "content_update_utc": pd.to_datetime(p.contentUpdateDate, errors="coerce")})
    log.append((prog, "missing funding scheme set to 'NOT_REPORTED'", int(proj.scheme_code.isna().sum())))
    proj["scheme_code"] = proj.scheme_code.fillna("NOT_REPORTED")
    # main programme part: the legal basis flagged uniqueProgrammePart (project.legalBasis can list several codes in H2020)
    main = (lb[lb.uniqueProgrammePart.map(to_bool) == True].assign(project_id=lambda x: x.projectID.astype("int64"))  # noqa: E712
            .drop_duplicates("project_id").set_index("project_id").legalBasis)
    fallback = p.legalBasis.str.split(";").str[0].values
    proj["main_part_code"] = proj.project_id.map(main).fillna(pd.Series(fallback, index=proj.index))
    log.append((prog, "main programme part taken from legalBasis.csv (project.legalBasis multi-valued)",
                int(p.legalBasis.str.contains(";").sum())))
    zero_cost = int((proj.total_cost == 0).sum())
    proj.loc[proj.total_cost == 0, "total_cost"] = np.nan          # 0 = not reported (lump sum / unit cost)
    log.append((prog, "project.total_cost = 0 set to NULL (not reported)", zero_cost))
    for col in ("signature_date", "start_date", "end_date"):
        proj[col] = pd.to_datetime(proj[col])

    calls = proj[["call_code"]].drop_duplicates().assign(programme_code=prog)
    topics = (tp.rename(columns={"topic": "topic_code"}).groupby("topic_code").title.first().reset_index()
              .assign(programme_code=prog))
    topics = pd.concat([topics, pd.DataFrame({"topic_code": sorted(set(proj.topic_code) - set(topics.topic_code)),
                                              "title": None, "programme_code": prog})])
    schemes = proj[["scheme_code"]].drop_duplicates().assign(programme_code=prog)
    schemes["action_family"] = schemes.scheme_code.map(action_family)

    ppp = (lb.rename(columns={"projectID": "project_id", "legalBasis": "part_code"})
           .assign(project_id=lambda x: x.project_id.astype("int64"), is_main=lambda x: x.uniqueProgrammePart.map(lambda v: to_bool(v) is True))
           .groupby(["project_id", "part_code"], as_index=False).is_main.max())

    # science domains (EuroSciVoc paths)
    esv = esv.dropna(subset=["euroSciVocCode"])
    dom_rows = {}
    for code, path in esv[["euroSciVocCode", "euroSciVocPath"]].drop_duplicates().itertuples(index=False):
        segs, labels = code.strip("/").split("/"), (path or "").split("/")
        if len(labels) != len(segs):
            labels = [None] * (len(segs) - 1) + [labels[-1]]
        for i in range(len(segs)):
            c = "/" + "/".join(segs[: i + 1])
            if c not in dom_rows or dom_rows[c] is None:
                dom_rows[c] = labels[i]
    domains = pd.DataFrame({"domain_code": list(dom_rows), "path_label": list(dom_rows.values())})
    psd = (esv.rename(columns={"projectID": "project_id", "euroSciVocCode": "domain_code"})[["project_id", "domain_code"]]
           .drop_duplicates().assign(project_id=lambda x: x.project_id.astype("int64")))

    # organisations and participations
    o = o.copy()
    multi = o.country.fillna("").str.contains(";")
    log.append((prog, "multi-valued country (e.g. 'DE;HU'): first code kept", int(multi.sum())))
    o["country_code"] = o.country.fillna("").str.split(";").str[0].map(country_iso2)
    o["updated"] = pd.to_datetime(o.contentUpdateDate, errors="coerce")
    org = (o.sort_values("updated").groupby("organisationID").tail(1)
           .assign(organisation_id=lambda x: x.organisationID.astype("int64"), legal_name=lambda x: x.name.fillna(x.shortName),
                   name_key=lambda x: x.name.map(normalise_name))
           .rename(columns={"shortName": "short_name", "activityType": "type_code", "city": "city", "nutsCode": "nuts_code",
                            "organizationURL": "website_url"})
           [["organisation_id", "legal_name", "short_name", "name_key", "type_code", "country_code", "city", "nuts_code",
             "website_url", "updated"]])
    part = pd.DataFrame({
        "project_id": o.projectID.astype("int64"), "organisation_id": o.organisationID.astype("int64"), "role_code": o.role,
        "order_no": pd.to_numeric(o["order"], errors="coerce").fillna(0).astype(int),
        "ec_contribution": o.ecContribution.map(parse_amount), "net_ec_contribution": o.netEcContribution.map(parse_amount),
        "total_cost": o.totalCost.map(parse_amount), "is_sme": o.SME.map(to_bool),
        "has_ended": o.endOfParticipation.map(to_bool).fillna(False)})
    unfunded = part.role_code.isin([r[0] for r in ROLES if not r[2]])
    log.append((prog, "ec_contribution NULL for unfunded roles set to 0", int((unfunded & part.ec_contribution.isna()).sum())))
    part.loc[unfunded & part.ec_contribution.isna(), "ec_contribution"] = 0.0
    part.loc[unfunded & part.net_ec_contribution.isna(), "net_ec_contribution"] = 0.0

    docs = (wl.rename(columns={"id": "document_id", "projectID": "project_id", "type": "doc_type", "physUrl": "url"})
            [["document_id", "project_id", "doc_type", "url", "source"]].dropna(subset=["document_id", "url"]))
    dup_docs = int(docs.document_id.duplicated().sum())
    docs = docs.drop_duplicates("document_id").assign(project_id=lambda x: x.project_id.astype("int64"))
    docs = docs[docs.project_id.isin(proj.project_id)]
    log.append((prog, "duplicate document ids dropped", dup_docs))

    return {"programme_part": parts, "call": calls, "topic": topics, "funding_scheme": schemes, "project": proj,
            "project_programme_part": ppp, "domains": domains, "project_science_domain": psd, "organisation": org,
            "participation": part, "project_document": docs}


def combine(frames: list[dict]) -> dict[str, pd.DataFrame]:
    out = {k: pd.concat([f[k] for f in frames], ignore_index=True) for k in frames[0]}
    # one row per organisation across programmes: most recent CORDIS record wins (PIC = key)
    out["organisation"] = out["organisation"].sort_values("updated").groupby("organisation_id").tail(1).drop(columns="updated")
    out["call"] = out["call"].drop_duplicates("call_code")
    out["topic"] = out["topic"].drop_duplicates("topic_code")
    out["funding_scheme"] = out["funding_scheme"].drop_duplicates("scheme_code")
    # the same web link can be listed under an H2020 and a Horizon Europe project (follow-up grants): keep the first
    out["project_document"] = out["project_document"].drop_duplicates("document_id")
    # science domains: official EuroSciVoc label and URI when the notation exists in EU Vocabularies
    dom = out.pop("domains").sort_values("path_label", na_position="last").drop_duplicates("domain_code")
    esv = pd.read_csv(REF / "euroscivoc_concepts.csv", dtype=str).drop_duplicates("notation").set_index("notation")
    dom["notation"] = dom.domain_code.str.rsplit("/", n=1).str[-1]
    dom["euroscivoc_uri"] = dom.notation.map(esv.concept)
    dom["label"] = (dom.notation.map(esv.label).fillna(dom.path_label.replace("", None))
                    .fillna("unlabelled CORDIS concept " + dom.notation))
    dom["parent_code"] = dom.domain_code.map(domain_parent)
    dom["depth"] = dom.domain_code.str.count("/")
    out["science_domain"] = dom[["domain_code", "notation", "label", "parent_code", "depth", "euroscivoc_uri"]]
    part = out["participation"].sort_values(["project_id", "order_no", "role_code"]).reset_index(drop=True)
    part.insert(0, "participation_id", np.arange(1, len(part) + 1, dtype="int64"))
    out["participation"] = part
    return out


ORDER = ["framework_programme", "country", "organisation_type", "participant_role", "load_batch", "programme_part",
         "funding_scheme", "science_domain", "call", "topic", "project", "project_programme_part", "project_science_domain",
         "project_document", "organisation", "participation"]
HIERARCHIES = {"programme_part": ("depth", "parent_part_code"), "science_domain": ("depth", "parent_code")}


def insert(con, table: str, df: pd.DataFrame):
    cols = [r[0] for r in con.execute(f"select column_name from duckdb_columns() where table_name = '{table}' "
                                      "order by column_index").fetchall()]
    df = df[[c for c in cols if c in df.columns]]
    if table in HIERARCHIES:
        level, _ = HIERARCHIES[table]
        for _, chunk in df.sort_values(level).groupby(level, sort=True):
            con.register("chunk", chunk)
            con.execute(f"insert into {table} ({', '.join(chunk.columns)}) select * from chunk")
    else:
        con.register("chunk", df)
        con.execute(f"insert into {table} ({', '.join(df.columns)}) select * from chunk")
    con.unregister("chunk")


def batches(stats: pd.DataFrame) -> pd.DataFrame:
    dl = pd.read_csv(RAW / "download_log.csv") if (RAW / "download_log.csv").exists() else pd.DataFrame(columns=["url", "downloaded_utc"])
    rows = []
    for i, (prog, g) in enumerate(stats.groupby("programme", sort=False), start=1):
        url = f"https://cordis.europa.eu/data/cordis-{'HORIZON' if prog == 'HORIZON' else 'h2020'}projects-csv.zip"
        d = dl[dl.url == url].downloaded_utc
        rows.append({"batch_id": i, "programme_code": prog, "source_url": url,
                     "downloaded_utc": pd.to_datetime(d.iloc[-1]).tz_localize(None) if len(d) else None,
                     "loaded_utc": dt.datetime.now(dt.timezone.utc).replace(tzinfo=None, microsecond=0),
                     "rows_read": int(g.rows.sum()), "lines_repaired": int(g.repaired_lines.sum()),
                     "lines_rejected": int(g.rejected_lines.sum())})
    return pd.DataFrame(rows)


def main(argv=None):
    argv = argv or sys.argv[1:]
    base = Path(argv[argv.index("--interim") + 1]) if "--interim" in argv else INTERIM
    db = Path(argv[argv.index("--db") + 1]) if "--db" in argv else DB
    raw = Path(argv[argv.index("--raw-dir") + 1]) if "--raw-dir" in argv else RAW
    stats = pd.read_csv(base / "parse_stats.csv") if "--skip-stage" in argv else stage(raw, base)
    progs = [p for p in PROGRAMMES if p in set(stats.programme)]
    log = []
    frames = [build_programme(p, base, log) for p in progs]
    data = combine(frames)
    used = set(data["organisation"].country_code.dropna())
    data.update(reference_tables(used))
    data["framework_programme"] = data["framework_programme"][data["framework_programme"].programme_code.isin(progs)]
    lb = batches(stats)
    data["load_batch"] = lb
    data["project"] = data["project"].merge(lb[["programme_code", "batch_id"]], on="programme_code")

    db.unlink(missing_ok=True)
    con = duckdb.connect(str(db))
    con.execute(DDL.read_text(encoding="utf-8"))
    for t in ORDER:
        insert(con, t, data[t])
    con.execute(MART.read_text(encoding="utf-8"))
    pd.DataFrame(log, columns=["programme", "rule", "rows"]).to_csv(base / "cleaning_log.csv", index=False)
    counts = {t: con.execute(f"select count(*) from {t}").fetchone()[0] for t in ORDER}
    con.close()
    from quality import run_checks
    qa = run_checks(db, base)
    print("Loaded:", ", ".join(f"{t}={n:,}" for t, n in counts.items()))
    print(f"Quality checks: {int((qa.status == 'PASS').sum())} pass, {int((qa.status == 'WARN').sum())} warn, "
          f"{int((qa.status == 'FAIL').sum())} fail")
    return counts, qa


if __name__ == "__main__":
    main()
