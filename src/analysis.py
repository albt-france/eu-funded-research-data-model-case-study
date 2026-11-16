"""Answer the business questions: run every sql/us*.sql on the database, save the results, compute headline figures.
PUBLIC DATA. Outputs: data/processed/us*.csv and data/processed/findings.json (every number in the report comes from here).
Usage: python src/analysis.py [--db data/cordis.duckdb]
"""
import json
import sys
from pathlib import Path

import duckdb
import networkx as nx
import pandas as pd

from config import DB, PROC, ROOT

SQL = ROOT / "sql"


def run_all(con) -> dict[str, pd.DataFrame]:
    out = {}
    for f in sorted(SQL.glob("us*.sql")):
        df = con.execute(f.read_text(encoding="utf-8")).df()
        df.to_csv(PROC / f"{f.stem}.csv", index=False, encoding="utf-8")
        out[f.stem] = df
    return out


def network_metrics(pairs: pd.DataFrame, top: int = 30) -> dict:
    """Country cooperation graph: degree and weighted centrality (descriptive, not a ranking of merit)."""
    g = nx.Graph()
    for r in pairs.itertuples():
        g.add_edge(r.country_a, r.country_b, weight=int(r.shared_projects))
    strength = dict(g.degree(weight="weight"))
    dens = nx.density(g)
    return {"countries": g.number_of_nodes(), "links": g.number_of_edges(), "density": round(dens, 3),
            "top_strength": sorted(strength.items(), key=lambda kv: -kv[1])[:top]}


def findings(con, r: dict[str, pd.DataFrame]) -> dict:
    q = lambda s: con.execute(s).fetchone()  # noqa: E731
    he, h2020 = "HORIZON", "H2020"
    f = {}
    for prog in (he, h2020):
        n, tot = q(f"select count(*), sum(ec_max_contribution) from project where programme_code = '{prog}'")
        parts, orgs = q(f"select count(*), count(distinct organisation_id) from participation x join project p using (project_id) "
                        f"where p.programme_code = '{prog}'")
        countries = q(f"select count(distinct o.country_code) from participation x join project p using (project_id) "
                      f"join organisation o using (organisation_id) where p.programme_code = '{prog}'")[0]
        f[prog] = {"projects": n, "eu_contribution": float(tot), "participations": parts, "organisations": orgs,
                   "countries": countries}
    f["HORIZON"]["status"] = dict(con.execute("select status, count(*) from project where programme_code = 'HORIZON' group by 1").fetchall())
    c = r["us02_funding_by_country"]
    tot = c.eu_contribution_bn.sum()
    f["eu27_share"] = float(c[c.is_eu27 == True].eu_contribution_bn.sum() / tot)  # noqa: E712
    f["top5_country_share"] = float(c.head(5).eu_contribution_bn.sum() / tot)
    f["top5_countries"] = c.head(5).country.tolist()
    t = r["us03_funding_by_org_type"]
    f["org_type_share_he"] = dict(zip(t[t.programme_code == he].type_code.fillna("NA"), t[t.programme_code == he].share_pct))
    cs = r["us05_consortium_size"]
    f["single_beneficiary_share_he"] = float(q("select avg(case when consortium_size = 1 then 1 else 0 end) from mart.dim_project "
                                               "where programme_code = 'HORIZON'")[0])
    f["consortium_by_family"] = cs.set_index("action_family")[["projects", "median_members", "avg_countries"]].to_dict("index")
    d = r["us04_funding_by_domain"]
    f["domain_he"] = d[d.programme_code == he].set_index("domain").eu_contribution_bn.to_dict()
    f["unclassified_share_he"] = float(q("select avg(case when not exists (select 1 from project_science_domain d where "
                                         "d.project_id = p.project_id) then 1 else 0 end) from project p where programme_code = 'HORIZON'")[0])
    f["network"] = network_metrics(r["us07_country_network"])
    f["sme"] = r["us12_sme_participation"].set_index("programme_code").to_dict("index")
    f["ai_drilldown"] = r["us10_domain_drilldown"].iloc[0].to_dict()
    f["data_date"] = str(q("select max(content_update_utc) from project where programme_code = 'HORIZON'")[0])[:10]
    return f


def main(argv=None):
    argv = argv or sys.argv[1:]
    db = Path(argv[argv.index("--db") + 1]) if "--db" in argv else DB
    PROC.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db), read_only=True)
    r = run_all(con)
    f = findings(con, r)
    con.close()
    (PROC / "findings.json").write_text(json.dumps(f, indent=2, default=float), encoding="utf-8")
    print(json.dumps({k: f[k] for k in ("HORIZON", "H2020", "eu27_share", "top5_country_share", "single_beneficiary_share_he",
                                        "unclassified_share_he", "sme", "ai_drilldown")}, indent=1, default=float))
    return r, f


if __name__ == "__main__":
    main()
