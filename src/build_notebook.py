"""Build and execute notebooks/analysis.ipynb: one section per user story, with the SQL (read from sql/) and its result,
plus one live SPARQL query on the graph. PUBLIC DATA.
Usage: python src/build_notebook.py   (needs data/cordis.duckdb and semantic/graph/horizon_ai_sample.ttl)
"""
import nbformat as nbf
from nbconvert.preprocessors import ExecutePreprocessor

from config import ROOT

STORIES = [
    ("us01_funding_by_pillar", "US01 - Where is the budget committed? Funding by programme and pillar", True),
    ("us02_funding_by_country", "US02 - Geographic spread: funding, participations and coordinations by country", True),
    ("us03_funding_by_org_type", "US03 - Who receives the funding? Organisation types", False),
    ("us04_funding_by_domain", "US04 - Funding by scientific domain, without double counting (weighted bridge)", False),
    ("us05_consortium_size", "US05 - What does a consortium look like, by type of action?", False),
    ("us06_duration_and_size", "US06 - Grant size and duration by type of action", False),
    ("us07_country_network", "US07 - Which countries work together?", True),
    ("us08_projects_by_start_year", "US08 - Projects by start year, two programmes", False),
    ("us09_coordination_share", "US09 - Coordinations per participation, all actions and collaborative actions only", True),
    ("us10_domain_drilldown", "US10 - A domain and all its sub-domains (recursive SQL)", False),
    ("us11_lineage", "US11 - Lineage: where does each row come from?", False),
    ("us12_sme_participation", "US12 - SME participation", False),
]


def main():
    nb = nbf.v4.new_notebook()
    c = [nbf.v4.new_markdown_cell(
        "# Horizon Europe: business questions answered on the data model\n\n"
        "**PUBLIC DATA**: CORDIS (Publications Office of the EU), Horizon Europe and Horizon 2020, downloaded 16 November 2026. "
        "Each section is a user story from `docs/analysis/REQUIREMENTS.md`; the SQL is read from `sql/` and runs on the DuckDB "
        "database built by `src/load.py`. Amounts are **maximum EU contributions** of signed grants (commitments, not payments). "
        "Descriptive figures only: they do not rank organisations or countries."),
         nbf.v4.new_code_cell(
        "import duckdb, pandas as pd\nfrom pathlib import Path\nROOT = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()\n"
        "con = duckdb.connect(str(ROOT / 'data' / 'cordis.duckdb'), read_only=True)\npd.set_option('display.max_columns', 12)\n"
        "def run(name, head=12):\n    sql = (ROOT / 'sql' / f'{name}.sql').read_text(encoding='utf-8')\n    print(sql)\n"
        "    return con.execute(sql).df().head(head)"),
         nbf.v4.new_markdown_cell("## Quality report of the load\nEighteen checks run after each load (`src/quality.py`). "
                                  "FAIL would stop the load; WARN are known properties of the source, explained in "
                                  "`docs/analysis/DATA_PROFILING.md`."),
         nbf.v4.new_code_cell("pd.read_csv(ROOT / 'data' / 'processed' / 'qa_report.csv')")]
    for name, title, _ in STORIES:
        c.append(nbf.v4.new_markdown_cell(f"## {title}"))
        c.append(nbf.v4.new_code_cell(f"run('{name}')"))
    c += [nbf.v4.new_markdown_cell(
        "## The same drill-down in SPARQL, on the ontology-aligned graph\n"
        "The graph (`semantic/graph/horizon_ai_sample.ttl`) maps the model to SKOS, W3C ORG, FOAF, DCAT and Dublin Core. "
        "`skos:broader*` follows the EuroSciVoc tree at any depth: the result must match US10 (1,263 projects)."),
          nbf.v4.new_code_cell(
        "from rdflib import Graph\ng = Graph().parse(ROOT / 'semantic' / 'graph' / 'horizon_ai_sample.ttl')\n"
        "q = '''PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nPREFIX dcterms: <http://purl.org/dc/terms/>\n"
        "SELECT (COUNT(DISTINCT ?p) AS ?projects) WHERE {\n  ?root skos:prefLabel \"artificial intelligence\"@en .\n"
        "  ?d skos:broader* ?root . ?p dcterms:subject ?d }'''\nprint(len(g), 'triples'); [int(r[0]) for r in g.query(q)]"),
          nbf.v4.new_markdown_cell("## Limits\n- Amounts are commitments; most Horizon Europe projects are still running.\n"
                                   "- 18% of Horizon Europe projects have no EuroSciVoc domain in CORDIS.\n"
                                   "- Coordination rates depend on the mix of single-beneficiary grants (ERC, MSCA, EIC) and on "
                                   "association rules, which are not analysed here.")]
    nb["cells"] = c
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    ExecutePreprocessor(timeout=600, kernel_name="python3").preprocess(nb, {"metadata": {"path": str(ROOT / "notebooks")}})
    out = ROOT / "notebooks" / "analysis.ipynb"
    out.parent.mkdir(exist_ok=True)
    nbf.write(nb, out)
    print("notebook:", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
