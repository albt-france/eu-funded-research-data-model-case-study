"""The physical model enforces the business rules: every bad row below must be rejected by the database."""
import duckdb
import pglast
import pytest

from config import DDL, MART, ROOT

BASE = """
insert into framework_programme values ('HORIZON', 'Horizon Europe', 2021, 2027, 'Regulation (EU) 2021/695', null);
insert into programme_part values ('HORIZON.2', 'HORIZON', null, 'Pillar II', 1);
insert into programme_part values ('HORIZON.2.5', 'HORIZON', 'HORIZON.2', 'Climate, Energy and Mobility', 2);
insert into funding_scheme values ('HORIZON-RIA', 'HORIZON', 'Research and innovation action');
insert into call values ('C1', 'HORIZON');
insert into topic values ('T1', 'HORIZON', 'Topic');
insert into load_batch values (1, 'HORIZON', 'https://example.org', null, now()::timestamp, 1, 0, 0);
insert into country values ('FR', 'FRA', 'FR', 'France', true, null);
insert into organisation_type values ('HES', 'Higher education');
insert into participant_role values ('coordinator', 'coordinator', true, 'Coordinator');
insert into organisation values (111, 'Org', null, 'ORG', 'HES', 'FR', null, null, null);
insert into project (project_id, acronym, title, status, programme_code, main_part_code, call_code, topic_code, scheme_code,
                     start_date, end_date, ec_max_contribution, batch_id)
values (1, 'P', 'Project', 'SIGNED', 'HORIZON', 'HORIZON.2.5', 'C1', 'T1', 'HORIZON-RIA', '2024-01-01', '2026-12-31', 100, 1);
insert into participation values (1, 1, 111, 'coordinator', 1, 100, 100, 100, false, false);
"""


@pytest.fixture()
def con():
    c = duckdb.connect()
    c.execute(DDL.read_text(encoding="utf-8"))
    c.execute(BASE)
    return c


@pytest.mark.parametrize("bad_sql", [
    # negative amount
    "insert into project (project_id, acronym, title, status, programme_code, main_part_code, call_code, topic_code, scheme_code, "
    "ec_max_contribution, batch_id) values (2, 'P', 'P', 'SIGNED', 'HORIZON', 'HORIZON.2.5', 'C1', 'T1', 'HORIZON-RIA', -5, 1)",
    # end before start
    "insert into project (project_id, acronym, title, status, programme_code, main_part_code, call_code, topic_code, scheme_code, "
    "start_date, end_date, ec_max_contribution, batch_id) values (2, 'P', 'P', 'SIGNED', 'HORIZON', 'HORIZON.2.5', 'C1', 'T1', "
    "'HORIZON-RIA', '2025-01-01', '2024-01-01', 5, 1)",
    # unknown status
    "insert into project (project_id, acronym, title, status, programme_code, main_part_code, call_code, topic_code, scheme_code, "
    "ec_max_contribution, batch_id) values (2, 'P', 'P', 'ONGOING', 'HORIZON', 'HORIZON.2.5', 'C1', 'T1', 'HORIZON-RIA', 5, 1)",
    # orphan foreign key (unknown topic)
    "insert into project (project_id, acronym, title, status, programme_code, main_part_code, call_code, topic_code, scheme_code, "
    "ec_max_contribution, batch_id) values (2, 'P', 'P', 'SIGNED', 'HORIZON', 'HORIZON.2.5', 'C1', 'NOPE', 'HORIZON-RIA', 5, 1)",
    # participation of an unknown organisation
    "insert into participation values (2, 1, 999, 'coordinator', 2, 0, 0, 0, false, false)",
    # duplicate participation (same project, organisation, role and order)
    "insert into participation values (2, 1, 111, 'coordinator', 1, 0, 0, 0, false, false)",
    # domain with an unknown parent
    "insert into science_domain values ('/99/1', '1', 'x', '/99', 2, null)",
    # role group outside the list
    "insert into participant_role values ('observer', 'observer', false, 'x')",
])
def test_constraints_reject_bad_rows(con, bad_sql):
    with pytest.raises(duckdb.Error):
        con.execute(bad_sql)


def test_mart_views_build_on_the_schema(con):
    con.execute(MART.read_text(encoding="utf-8"))
    assert con.execute("select pillar_title from mart.dim_project").fetchone()[0] == "Pillar II"
    assert con.execute("select sum(net_ec_contribution) from mart.fact_participation").fetchone()[0] == 100


@pytest.mark.parametrize("path", [DDL, MART, ROOT / "model" / "ddl" / "schema_postgres.sql"])
def test_ddl_is_valid_postgresql_syntax(path):
    """Parsed with the PostgreSQL parser (pglast); CI also applies the files to a real PostgreSQL server."""
    assert len(pglast.parse_sql(path.read_text(encoding="utf-8"))) > 0
