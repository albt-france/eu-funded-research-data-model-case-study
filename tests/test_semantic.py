"""Semantic layer on the SIMULATED fixtures: mapping, SPARQL with property paths, SHACL rules."""
import duckdb
import pytest
from rdflib import Graph
from rdflib.namespace import ORG, RDF

import build_rdf
from build_rdf import PREFIX_TEXT, QUERIES, ROLE, build_graph, validate


@pytest.fixture(scope="module")
def graph(loaded):
    with duckdb.connect(str(loaded["db"]), read_only=True) as con:
        return build_graph(con, "/23")          # natural sciences and everything below


def test_projects_and_memberships_are_mapped(graph):
    assert len(set(graph.subjects(RDF.type, ORG.Membership))) == 7     # projects 900001 and 900002
    assert len(set(graph.subjects(RDF.type, ORG.OrganizationalCollaboration))) == 2


def test_transitive_domain_query_finds_sub_domains(graph):
    q = PREFIX_TEXT + """SELECT (COUNT(DISTINCT ?p) AS ?n) WHERE {
      ?root skos:notation "/23" . ?d skos:broader* ?root . ?p dcterms:subject ?d }"""
    assert int(list(graph.query(q))[0][0]) == 2


def test_countries_use_eu_authority_uris(graph):
    q = PREFIX_TEXT + "SELECT DISTINCT ?c WHERE { ?o dcterms:spatial ?c }"
    assert {str(r[0]).rsplit("/", 1)[-1] for r in graph.query(q)} >= {"GRC", "GBR", "DEU", "FRA"}


def test_company_names_are_not_published(graph):
    q = PREFIX_TEXT + "SELECT ?l WHERE { ?o org:identifier '222' ; skos:prefLabel ?l }"
    assert str(list(graph.query(q))[0][0]) == "Organisation PIC 222"


def test_shacl_conforms_and_ask_query(graph):
    conforms, report = validate(graph)
    assert conforms, report
    assert not graph.query(PREFIX_TEXT + QUERIES["graph_10_ask_no_coordinator"][1]).askAnswer


def test_shacl_rejects_a_project_without_coordinator(graph):
    broken = Graph()
    for t in graph:
        broken.add(t)
    for m in list(broken.subjects(ORG.role, ROLE.coordinator)):
        broken.remove((m, None, None))
    conforms, report = validate(broken)
    assert not conforms and "exactly one coordinator" in report


def test_all_graph_queries_parse(graph):
    for name, (_, body) in build_rdf.QUERIES.items():
        graph.query(PREFIX_TEXT + body)
