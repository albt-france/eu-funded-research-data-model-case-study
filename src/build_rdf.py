"""Semantic layer: an RDF graph of a sample of the database, mapped to existing vocabularies, queried with SPARQL and
validated with SHACL. PUBLIC DATA.

Sample: Horizon Europe projects classified under 'artificial intelligence' or any of its sub-domains (EuroSciVoc).
Vocabularies: SKOS (EuroSciVoc, programme parts, roles), W3C ORG (organisations, consortium memberships), FOAF (project,
page), Dublin Core and DCAT (titles, identifiers, periods, dataset metadata). Countries and EuroSciVoc concepts use the
official EU Vocabularies URIs. Only 5 local terms (semantic/vocabulary.ttl).
Publication rule: organisation names are written only for universities, research organisations and public bodies;
companies and 'other' entities are labelled by their PIC (a sole trader can carry a person's name).

Usage: python src/build_rdf.py [--db data/cordis.duckdb] [--domain /23/47/297]
Outputs: semantic/graph/horizon_ai_sample.ttl, semantic/queries/graph_*.rq, semantic/results/graph_*.csv,
         semantic/results/shacl_report.txt, data/processed/semantic_summary.json
"""
import datetime as dt
import json
import sys
from decimal import Decimal
from pathlib import Path

import duckdb
import pandas as pd
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCAT, DCTERMS, FOAF, ORG, PROV, RDF, SKOS, XSD

from config import DB, PROC, SEM

CS = Namespace("https://example.org/cordis/vocab#")
EX = Namespace("https://example.org/cordis/")
ROLE = Namespace("https://example.org/cordis/role/")
COUNTRY = "http://publications.europa.eu/resource/authority/country/"
NAMED_TYPES = {"HES", "REC", "PUB"}
DEFAULT_DOMAIN = "/23/47/297"   # EuroSciVoc 'artificial intelligence'

QUERIES = {
    "graph_01_domain_tree": ("Projects in a domain and all its sub-domains (SKOS transitive path)", """
SELECT ?domain ?label (COUNT(DISTINCT ?project) AS ?projects) WHERE {
  ?root skos:prefLabel "artificial intelligence"@en .
  ?domain skos:broader* ?root ; skos:prefLabel ?label .
  ?project a foaf:Project ; dcterms:subject ?domain .
} GROUP BY ?domain ?label ORDER BY DESC(?projects)"""),
    "graph_02_funding_by_country": ("EU contribution by participant country (sum over consortium memberships)", """
SELECT ?country (COUNT(DISTINCT ?project) AS ?projects) (SUM(?amount) AS ?eu_contribution) WHERE {
  ?m a org:Membership ; org:member ?o ; org:organization ?project ; cs:netEcContribution ?amount .
  ?o dcterms:spatial ?country .
} GROUP BY ?country ORDER BY DESC(?eu_contribution) LIMIT 15"""),
    "graph_03_country_pairs": ("Country pairs that work together most often (two members of the same consortium)", """
SELECT ?c1 ?c2 (COUNT(DISTINCT ?project) AS ?shared_projects) WHERE {
  ?m1 org:organization ?project ; org:member/dcterms:spatial ?c1 .
  ?m2 org:organization ?project ; org:member/dcterms:spatial ?c2 .
  FILTER (STR(?c1) < STR(?c2))
} GROUP BY ?c1 ?c2 ORDER BY DESC(?shared_projects) LIMIT 15"""),
    "graph_04_coordinators_by_type": ("Who coordinates: coordinators by organisation type", """
SELECT ?type (COUNT(*) AS ?coordinations) WHERE {
  ?m org:role role:coordinator ; org:member ?o .
  ?o org:classification/skos:prefLabel ?type .
} GROUP BY ?type ORDER BY DESC(?coordinations)"""),
    "graph_05_broad_consortia": ("Projects whose consortium spans the most countries", """
SELECT ?acronym (COUNT(DISTINCT ?country) AS ?countries) (COUNT(DISTINCT ?o) AS ?members) WHERE {
  ?project a foaf:Project ; skos:altLabel ?acronym .
  ?m org:organization ?project ; org:member ?o . ?o dcterms:spatial ?country .
} GROUP BY ?acronym ORDER BY DESC(?countries) LIMIT 10"""),
    "graph_06_domain_cooccurrence": ("Domains assigned together to the same project (beyond AI itself)", """
SELECT ?l1 ?l2 (COUNT(DISTINCT ?p) AS ?projects) WHERE {
  ?p dcterms:subject ?d1, ?d2 .
  ?d1 skos:prefLabel ?l1 . ?d2 skos:prefLabel ?l2 .
  FILTER (STR(?l1) < STR(?l2))
} GROUP BY ?l1 ?l2 ORDER BY DESC(?projects) LIMIT 10"""),
    "graph_07_local_to_official": ("CORDIS-only concepts and the official EuroSciVoc concept they hang under", """
SELECT ?local ?label ?official ?official_label WHERE {
  ?local a skos:Concept ; skos:prefLabel ?label ; skos:broader+ ?official .
  ?official skos:prefLabel ?official_label .
  FILTER (STRSTARTS(STR(?local), "https://example.org/"))
  FILTER (STRSTARTS(STR(?official), "http://data.europa.eu/8mn/euroscivoc"))
  FILTER NOT EXISTS { ?local skos:broader+ ?mid . ?mid skos:broader+ ?official .
                      FILTER (STRSTARTS(STR(?mid), "http://data.europa.eu/8mn/euroscivoc")) }
} ORDER BY ?label"""),
    "graph_08_ongoing": ("Ongoing projects (end date after the data date) and their maximum EU contribution", """
SELECT (COUNT(?p) AS ?ongoing_projects) (SUM(?max) AS ?eu_max_contribution) WHERE {
  ?p a foaf:Project ; cs:ecMaxContribution ?max ; dcterms:temporal/dcat:endDate ?end .
  FILTER (?end > "2026-11-16"^^xsd:date)
}"""),
    "graph_09_sme_share": ("Share of participations declared by SMEs, by programme part", """
SELECT ?part (COUNT(?m) AS ?participations) (SUM(IF(?sme, 1, 0)) AS ?sme_participations) WHERE {
  ?p cs:fundedUnder/skos:prefLabel ?part .
  ?m org:organization ?p ; cs:isSme ?sme .
} GROUP BY ?part ORDER BY DESC(?participations) LIMIT 10"""),
    "graph_10_ask_no_coordinator": ("ASK: is there a project without a coordinator? (expected: false)", """
ASK {
  ?p a foaf:Project .
  FILTER NOT EXISTS { ?m org:organization ?p ; org:role role:coordinator }
}"""),
}
PREFIX_TEXT = """PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX org: <http://www.w3.org/ns/org#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX cs: <https://example.org/cordis/vocab#>
PREFIX role: <https://example.org/cordis/role/>
"""


def dec(x) -> Literal:
    return Literal(Decimal(str(round(float(x), 2))), datatype=XSD.decimal)


def concept_uri(code: str, official: str | None) -> URIRef:
    return URIRef(official) if isinstance(official, str) and official else EX[f"domain{code}"]


def build_graph(con, domain: str, programme: str = "HORIZON") -> Graph:
    g = Graph()
    for p, ns in (("skos", SKOS), ("org", ORG), ("foaf", FOAF), ("dcat", DCAT), ("dcterms", DCTERMS), ("cs", CS),
                  ("role", ROLE), ("prov", PROV), ("ex", EX)):
        g.bind(p, ns)
    pids = [r[0] for r in con.execute(
        "select distinct psd.project_id from project_science_domain psd join project p using (project_id) "
        "where p.programme_code = ? and (psd.domain_code = ? or psd.domain_code like ? || '/%')",
        [programme, domain, domain]).fetchall()]
    con.register("sample_ids", pd.DataFrame({"project_id": pids}))

    # dataset metadata (DCAT)
    ds = EX["dataset/horizon-ai-sample"]
    g.add((ds, RDF.type, DCAT.Dataset))
    g.add((ds, DCTERMS.title, Literal("Horizon Europe projects in artificial intelligence (sample graph)", lang="en")))
    g.add((ds, DCTERMS.source, URIRef("https://cordis.europa.eu/data/cordis-HORIZONprojects-csv.zip")))
    g.add((ds, DCTERMS.license, URIRef("http://data.europa.eu/eli/dec/2011/833/oj")))
    g.add((ds, DCTERMS.issued, Literal(dt.date.today().isoformat(), datatype=XSD.date)))
    g.add((ds, PROV.wasDerivedFrom, URIRef("https://cordis.europa.eu/")))

    # SKOS: EuroSciVoc concepts (official URIs, local URIs for CORDIS-only levels)
    dom = con.execute("select domain_code, label, parent_code, euroscivoc_uri from science_domain").df()
    uri = {r.domain_code: concept_uri(r.domain_code, r.euroscivoc_uri) for r in dom.itertuples()}
    esv_scheme = URIRef("http://data.europa.eu/8mn/euroscivoc#40c0f173-baa3-48a3-9fe6-d6e8fb366a00")
    used = set(con.execute("select distinct domain_code from project_science_domain join sample_ids using (project_id)").df().domain_code)
    keep = set()
    for c in used:  # every used concept and all its ancestors
        while c:
            keep.add(c)
            c = dom.set_index("domain_code").parent_code.get(c)
            c = c if isinstance(c, str) else None
    for r in dom[dom.domain_code.isin(keep)].itertuples():
        u = uri[r.domain_code]
        g.add((u, RDF.type, SKOS.Concept))
        g.add((u, SKOS.prefLabel, Literal(r.label, lang="en")))
        g.add((u, SKOS.notation, Literal(r.domain_code)))
        g.add((u, SKOS.inScheme, esv_scheme if str(u).startswith("http://data.europa.eu") else EX["scheme/cordis-domains"]))
        if isinstance(r.parent_code, str):
            g.add((u, SKOS.broader, uri[r.parent_code]))

    # SKOS: roles (org:Role is a subclass of skos:Concept) and organisation types
    for code, group, label in con.execute("select role_code, role_group, label from participant_role").fetchall():
        grp = ROLE[f"group/{group.replace(' ', '-')}"]
        g.add((ROLE[code], RDF.type, ORG.Role))
        g.add((ROLE[code], RDF.type, SKOS.Concept))
        g.add((ROLE[code], SKOS.prefLabel, Literal(label.split(":")[0].split("(")[0].strip(), lang="en")))
        g.add((ROLE[code], SKOS.broader, grp))
        g.add((grp, RDF.type, SKOS.Concept))
        g.add((grp, SKOS.prefLabel, Literal(group, lang="en")))
    for code, label in con.execute("select type_code, label from organisation_type").fetchall():
        t = EX[f"orgtype/{code}"]
        g.add((t, RDF.type, SKOS.Concept))
        g.add((t, SKOS.prefLabel, Literal(label, lang="en")))
        g.add((t, SKOS.notation, Literal(code)))

    # programme parts (SKOS hierarchy)
    parts = con.execute("select part_code, title, parent_part_code from programme_part where programme_code = ?",
                        [programme]).fetchall()
    for code, title, parent in parts:
        u = EX[f"programme-part/{code}"]
        g.add((u, RDF.type, SKOS.Concept))
        g.add((u, SKOS.prefLabel, Literal(title, lang="en")))
        g.add((u, SKOS.notation, Literal(code)))
        if parent:
            g.add((u, SKOS.broader, EX[f"programme-part/{parent}"]))

    # projects: foaf:Project and org:OrganizationalCollaboration ("a collaboration between organizations, such as a project")
    pr = con.execute("select p.project_id, p.acronym, p.title, p.start_date, p.end_date, p.ec_max_contribution, "
                     "p.main_part_code, p.scheme_code from project p join sample_ids using (project_id)").df()
    for r in pr.itertuples():
        u = EX[f"project/{r.project_id}"]
        g.add((u, RDF.type, FOAF.Project))
        g.add((u, RDF.type, ORG.OrganizationalCollaboration))
        g.add((u, DCTERMS.identifier, Literal(str(r.project_id))))
        g.add((u, DCTERMS.title, Literal(r.title, lang="en")))
        g.add((u, SKOS.altLabel, Literal(r.acronym)))
        g.add((u, FOAF.page, URIRef(f"https://cordis.europa.eu/project/id/{r.project_id}")))
        g.add((u, CS.ecMaxContribution, dec(r.ec_max_contribution)))
        g.add((u, CS.fundedUnder, EX[f"programme-part/{r.main_part_code}"]))
        g.add((u, CS.fundingScheme, EX[f"scheme/{r.scheme_code}"]))
        g.add((u, DCTERMS.isPartOf, ds))
        if pd.notna(r.start_date):
            t = BNode()
            g.add((u, DCTERMS.temporal, t))
            g.add((t, RDF.type, DCTERMS.PeriodOfTime))
            g.add((t, DCAT.startDate, Literal(pd.Timestamp(r.start_date).date(), datatype=XSD.date)))
            g.add((t, DCAT.endDate, Literal(pd.Timestamp(r.end_date).date(), datatype=XSD.date)))
    for pid, code in con.execute("select project_id, domain_code from project_science_domain join sample_ids using (project_id)").fetchall():
        g.add((EX[f"project/{pid}"], DCTERMS.subject, uri[code]))

    # organisations (ORG) and memberships (n-ary relation: organisation x project x role x amount)
    orgs = con.execute("select o.organisation_id, o.legal_name, o.type_code, c.iso3_code from organisation o "
                       "left join country c using (country_code) where o.organisation_id in "
                       "(select organisation_id from participation join sample_ids using (project_id))").df()
    for r in orgs.itertuples():
        u = EX[f"organisation/{r.organisation_id}"]
        g.add((u, RDF.type, ORG.Organization))
        g.add((u, ORG.identifier, Literal(str(r.organisation_id))))
        name = r.legal_name if r.type_code in NAMED_TYPES else f"Organisation PIC {r.organisation_id}"
        g.add((u, SKOS.prefLabel, Literal(name)))
        if isinstance(r.type_code, str):
            g.add((u, ORG.classification, EX[f"orgtype/{r.type_code}"]))
        if isinstance(r.iso3_code, str):
            g.add((u, DCTERMS.spatial, URIRef(COUNTRY + r.iso3_code)))
    mem = con.execute("select x.participation_id, x.project_id, x.organisation_id, x.role_code, x.net_ec_contribution, x.is_sme, "
                      "r.receives_eu_funding from participation x join participant_role r using (role_code) "
                      "join sample_ids using (project_id)").df()
    for r in mem.itertuples():
        m = EX[f"membership/{r.participation_id}"]
        g.add((m, RDF.type, ORG.Membership))
        g.add((m, ORG.member, EX[f"organisation/{r.organisation_id}"]))
        g.add((m, ORG.organization, EX[f"project/{r.project_id}"]))
        g.add((m, ORG.role, ROLE[r.role_code]))
        if r.receives_eu_funding and pd.notna(r.net_ec_contribution):
            g.add((m, CS.netEcContribution, dec(r.net_ec_contribution)))
        if pd.notna(r.is_sme):
            g.add((m, CS.isSme, Literal(bool(r.is_sme))))
    con.unregister("sample_ids")
    return g


def run_queries(g: Graph) -> dict:
    out = {}
    qdir, rdir = SEM / "queries", SEM / "results"
    qdir.mkdir(parents=True, exist_ok=True)
    rdir.mkdir(parents=True, exist_ok=True)
    for name, (title, body) in QUERIES.items():
        text = f"# {title}\n{PREFIX_TEXT}{body.strip()}\n"
        (qdir / f"{name}.rq").write_text(text, encoding="utf-8")
        res = g.query(text)
        if res.type == "ASK":
            df = pd.DataFrame({"answer": [bool(res.askAnswer)]})
        else:
            df = pd.DataFrame([[None if v is None else (float(v) if isinstance(v.toPython(), Decimal) else v.toPython())
                                for v in row] for row in res], columns=[str(v) for v in res.vars])
        df.to_csv(rdir / f"{name}.csv", index=False, encoding="utf-8")
        out[name] = df
    return out


def validate(g: Graph) -> tuple[bool, str]:
    from pyshacl import validate as shacl
    shapes = Graph().parse(SEM / "shapes.ttl")
    conforms, _, text = shacl(g, shacl_graph=shapes, inference="none", allow_warnings=True)
    return conforms, text


def main(argv=None):
    argv = argv or sys.argv[1:]
    db = Path(argv[argv.index("--db") + 1]) if "--db" in argv else DB
    domain = argv[argv.index("--domain") + 1] if "--domain" in argv else DEFAULT_DOMAIN
    con = duckdb.connect(str(db), read_only=True)
    g = build_graph(con, domain)
    con.close()
    (SEM / "graph").mkdir(parents=True, exist_ok=True)
    ttl = SEM / "graph" / "horizon_ai_sample.ttl"
    g.serialize(ttl, format="turtle", encoding="utf-8")
    res = run_queries(g)
    conforms, report = validate(g)
    (SEM / "results" / "shacl_report.txt").write_text(report, encoding="utf-8")
    summary = {"triples": len(g), "projects": len(set(g.subjects(RDF.type, FOAF.Project))),
               "organisations": len(set(g.subjects(RDF.type, ORG.Organization))),
               "memberships": len(set(g.subjects(RDF.type, ORG.Membership))),
               "concepts": len(set(g.subjects(RDF.type, SKOS.Concept))),
               "official_euroscivoc_concepts": len({s for s in g.subjects(RDF.type, SKOS.Concept)
                                                     if str(s).startswith("http://data.europa.eu/8mn/euroscivoc")}),
               "shacl_conforms": conforms, "queries": len(res), "ttl_kb": ttl.stat().st_size // 1024}
    PROC.mkdir(parents=True, exist_ok=True)
    (PROC / "semantic_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))
    return g, res, conforms


if __name__ == "__main__":
    main()
