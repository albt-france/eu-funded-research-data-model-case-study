"""End-to-end test on the SIMULATED fixture files (same format and same defects as the real CORDIS exports)."""
import duckdb
import pandas as pd


def q(loaded, sql):
    with duckdb.connect(str(loaded["db"]), read_only=True) as c:
        return c.execute(sql).fetchall()


def test_row_counts(loaded):
    c = loaded["counts"]
    assert c["project"] == 3 and c["participation"] == 10 and c["organisation"] == 7
    assert c["project_document"] == 2          # duplicate web link removed


def test_no_failed_quality_check(loaded):
    qa = loaded["qa"]
    assert (qa.status != "FAIL").all(), qa[qa.status == "FAIL"].to_string()


def test_quality_checks_find_the_planted_issues(loaded):
    qa = loaded["qa"].set_index("id").offending_rows
    assert qa["Q08"] == 1      # one unclassified project
    assert qa["Q10"] == 1      # duplicate organisation candidate (same name, different PIC)
    assert qa["Q11"] == 1      # signed after start
    assert qa["Q12"] >= 1      # 'solar thermal' code is not in the official EuroSciVoc
    assert qa["Q14"] == 1      # organisation leaving and re-joining


def test_broken_objective_is_repaired(loaded):
    obj = q(loaded, "select objective from project where project_id = 900001")[0][0]
    assert 'stray ";" separator' in obj and '"sweet spot"' in obj


def test_amounts_dates_and_codes_are_cleaned(loaded):
    assert float(q(loaded, "select ec_max_contribution from project where project_id = 900001")[0][0]) == 1000000.50
    assert q(loaded, "select total_cost from project where project_id = 900002")[0][0] is None   # 0 = not reported
    countries = dict(q(loaded, "select organisation_id, country_code from organisation"))
    assert countries[111] == "GR" and countries[222] == "GB" and countries[333] == "DE" and countries[666] == "XK"


def test_unfunded_role_gets_zero_and_affiliated_entity_keeps_net_amount(loaded):
    rows = dict(q(loaded, "select role_code, net_ec_contribution from participation where role_code in "
                          "('associatedPartner', 'thirdParty')"))
    assert float(rows["associatedPartner"]) == 0 and float(rows["thirdParty"]) == 100000


def test_sme_status_is_kept_per_participation(loaded):
    sme = q(loaded, "select project_id, is_sme from participation where organisation_id = 222 order by 1")
    assert sme == [(900001, True), (900003, False)]


def test_no_personal_or_address_data_in_the_database(loaded):
    cols = {r[0].lower() for r in q(loaded, "select column_name from duckdb_columns()")}
    for banned in ("street", "postcode", "vatnumber", "geolocation", "contactform", "email", "telephone"):
        assert not any(banned in c for c in cols)
    stage = pd.read_parquet(loaded["interim"] / "HORIZON_organization.parquet")
    assert not {"street", "postCode", "vatNumber", "geolocation", "contactForm"} & set(stage.columns)


def test_domain_hierarchy_and_official_alignment(loaded):
    rows = dict(q(loaded, "select domain_code, euroscivoc_uri from science_domain"))
    assert rows["/23/53/373"].startswith("http://data.europa.eu/8mn/euroscivoc#")   # electrochemistry: official concept
    assert rows["/25/67/425/1169/1685/85521413"] is None                           # CORDIS-only level
    assert q(loaded, "select parent_code from science_domain where domain_code = '/23/53/373'")[0][0] == "/23/53"


def test_star_schema_totals_match_the_model(loaded):
    fact = q(loaded, "select sum(net_ec_contribution) from mart.fact_participation")[0][0]
    assert float(fact) == 1000000.50 + 200000 + 500000
    pillars = dict(q(loaded, "select project_id, pillar_title from mart.dim_project"))
    assert pillars[900001].startswith("Pillar II") and pillars[900002].startswith("Pillar I ")
