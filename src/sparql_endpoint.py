"""Real SPARQL queries on the Publications Office endpoint (EU Vocabularies). PUBLIC DATA.

1. Reference extracts used by the pipeline (saved to data/reference/, small, versioned with their retrieval date):
   - EuroSciVoc concepts (URI, notation, English label, broader concept)  -> euroscivoc_concepts.csv
   - Country authority table (ISO alpha-2/alpha-3, EU code, English label) -> countries.csv
2. Three showcase queries (semantic/queries/endpoint_*.rq) with their results (semantic/results/endpoint_*.csv).

One request per query, results cached: rerun only with --refresh.
Endpoint: https://publications.europa.eu/webapi/rdf/sparql
"""
import datetime as dt
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "data" / "reference"
QDIR = ROOT / "semantic" / "queries"
RES = ROOT / "semantic" / "results"
ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"
ESV_SCHEME = "http://data.europa.eu/8mn/euroscivoc#40c0f173-baa3-48a3-9fe6-d6e8fb366a00"
ESV_GRAPH = "http://publications.europa.eu/resource/authority/euroscivoc"
PREFIXES = """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX euvoc: <http://publications.europa.eu/ontology/euvoc#>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
"""

Q_ESV = PREFIXES + f"""
# All EuroSciVoc concepts with their notation (= last segment of the CORDIS code), English label and broader concept
SELECT DISTINCT ?concept ?notation ?label ?broader WHERE {{
  GRAPH <{ESV_GRAPH}> {{
    ?concept skos:inScheme <{ESV_SCHEME}> ;
             skos:prefLabel ?label ;
             euvoc:xlNotation ?xl .
    ?xl rdf:value ?notation .
    OPTIONAL {{ ?concept skos:broader ?broader }}
    FILTER (lang(?label) = 'en')
    FILTER (STRSTARTS(STR(?concept), 'http://data.europa.eu/8mn/euroscivoc#'))
  }}
}}"""

Q_COUNTRY = PREFIXES + """
# EU country authority table: ISO 3166-1 alpha-2, EU interinstitutional code (EL, UK...), English label
SELECT DISTINCT ?country ?alpha3 ?alpha2 ?eu_code ?label WHERE {
  GRAPH <http://publications.europa.eu/resource/authority/country> {
    ?country dc:identifier ?alpha3 ;
             skos:prefLabel ?label ;
             skos:notation ?alpha2 .
    FILTER (lang(?label) = 'en' && datatype(?alpha2) = euvoc:ISO_3166_1_ALPHA_2)
    OPTIONAL { ?country skos:notation ?eu_code FILTER (datatype(?eu_code) = euvoc:ISG_COU) }
  }
}"""

SHOWCASE = {
    "endpoint_1_top_domains": PREFIXES + f"""
# Q1. The top concepts of EuroSciVoc and how many concepts sit below each one (transitive skos:broader+ path)
SELECT ?top ?label (COUNT(DISTINCT ?c) AS ?descendants) WHERE {{
  GRAPH <{ESV_GRAPH}> {{
    ?top skos:topConceptOf <{ESV_SCHEME}> ; skos:prefLabel ?label .
    ?c skos:broader+ ?top .
    FILTER (lang(?label) = 'en')
  }}
}} GROUP BY ?top ?label ORDER BY DESC(?descendants)""",
    "endpoint_2_multilingual": PREFIXES + f"""
# Q2. One concept, every official language: why a controlled vocabulary helps a multilingual EU system
SELECT ?lang ?label WHERE {{
  GRAPH <{ESV_GRAPH}> {{
    ?c skos:inScheme <{ESV_SCHEME}> ; skos:prefLabel "artificial intelligence"@en ; skos:prefLabel ?label .
    FILTER (STRSTARTS(STR(?c), 'http://data.europa.eu/8mn/euroscivoc#'))
  }}
  BIND (lang(?label) AS ?lang)
}} ORDER BY ?lang""",
    "endpoint_3_path": PREFIXES + f"""
# Q3. The full path of "machine learning" up to its top concept (property path), as CORDIS stores it in euroSciVocPath
SELECT ?ancestor ?label ?notation WHERE {{
  GRAPH <{ESV_GRAPH}> {{
    ?c skos:inScheme <{ESV_SCHEME}> ; skos:prefLabel "machine learning"@en ; skos:broader* ?ancestor .
    ?ancestor skos:prefLabel ?label ; euvoc:xlNotation/rdf:value ?notation .
    FILTER (lang(?label) = 'en')
    FILTER (STRSTARTS(STR(?c), 'http://data.europa.eu/8mn/euroscivoc#'))
    FILTER (STRSTARTS(STR(?ancestor), 'http://data.europa.eu/8mn/euroscivoc#'))
  }}
}}""",
}


def run(query: str, tries: int = 3) -> pd.DataFrame:
    for i in range(tries):
        try:
            return _run(query)
        except requests.RequestException:
            if i == tries - 1:
                raise
            time.sleep(10 * (i + 1))


def _run(query: str) -> pd.DataFrame:
    r = requests.get(ENDPOINT, params={"query": query, "format": "application/sparql-results+json"}, timeout=180,
                     headers={"User-Agent": "eu-open-data-case-study/1.0 (low frequency)"})
    r.raise_for_status()
    rows = [{k: v["value"] for k, v in b.items()} for b in r.json()["results"]["bindings"]]
    return pd.DataFrame(rows)


def save(df: pd.DataFrame, path: Path, query: str | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    if query:
        (QDIR / f"{path.stem}.rq").write_text(query.strip() + "\n", encoding="utf-8")


def main():
    refresh = "--refresh" in sys.argv
    today = dt.date.today().isoformat()
    log = []
    esv_file, ctry_file = REF / "euroscivoc_concepts.csv", REF / "countries.csv"
    if refresh or not esv_file.exists():
        esv = run(Q_ESV)
        nota = esv.drop_duplicates("concept").set_index("concept").notation
        esv["broader_notation"] = esv.broader.map(nota)
        esv = esv.drop(columns="broader").drop_duplicates("concept").sort_values("notation", key=lambda s: s.astype(int))
        save(esv, esv_file)
        log.append(("euroscivoc_concepts.csv", len(esv)))
    if refresh or not ctry_file.exists():
        c = run(Q_COUNTRY).sort_values("alpha3")
        c = c.groupby("country", as_index=False).first()
        save(c, ctry_file)
        log.append(("countries.csv", len(c)))
    for name, q in SHOWCASE.items():
        f = RES / f"{name}.csv"
        if refresh or not f.exists():
            df = run(q)
            save(df, f, q)
            log.append((f.name, len(df)))
    if log:
        meta = REF / "RETRIEVED.md"
        lines = meta.read_text(encoding="utf-8").splitlines() if meta.exists() else [
            "# Reference extracts from the Publications Office SPARQL endpoint", "",
            f"Endpoint: {ENDPOINT}. Licence: EU Vocabularies are reusable under the Commission's reuse policy "
            "(Decision 2011/833/EU, CC BY 4.0), with acknowledgement of the source.", "", "| File | Rows | Retrieved |", "|---|---|---|"]
        lines += [f"| {f} | {n} | {today} |" for f, n in log]
        meta.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for f, n in log:
        print(f"{f}: {n} rows")


if __name__ == "__main__":
    main()
