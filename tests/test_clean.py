import pandas as pd
import pytest

from clean import (country_iso2, domain_parent, drop_personal_columns, normalise_name, parse_amount, parse_date,
                   programme_part_parent, to_bool)
from cordis_io import split_line
from load import action_family


@pytest.mark.parametrize("raw, expected", [
    ("2073781,25", 2073781.25), ("2073781.25", 2073781.25), ("1500000", 1500000.0), ("1.234,56", 1234.56),
    ("1,234.56", 1234.56), ("0", 0.0), ("", None), (None, None), ("n/a", None), (" 12 ", 12.0)])
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == expected


def test_parse_date():
    assert parse_date("2022-09-01") == pd.Timestamp("2022-09-01")
    assert parse_date("2026-11-04 16:50:11") == pd.Timestamp("2026-11-04")
    assert parse_date("31/12/2022") is None and parse_date("") is None and parse_date(None) is None


@pytest.mark.parametrize("raw, expected", [("EL", "GR"), ("UK", "GB"), ("de", "DE"), ("XK", "XK"), ("", None), (None, None)])
def test_country_iso2(raw, expected):
    assert country_iso2(raw) == expected


def test_to_bool():
    assert to_bool("true") is True and to_bool("false") is False and to_bool("") is None and to_bool(None) is None


def test_normalise_name_removes_case_accents_punctuation_and_legal_form():
    assert normalise_name("Université Côte d'Azur") == "UNIVERSITE COTE D AZUR"
    assert normalise_name("SIMULATED COMPANY B GMBH") == normalise_name("Simulated Company B.") == "SIMULATED COMPANY B"
    assert normalise_name("") is None and normalise_name(None) is None


def test_drop_personal_columns_covers_old_contact_fields():
    df = pd.DataFrame(columns=["name", "country", "street", "postCode", "vatNumber", "geolocation", "contactForm",
                               "contactFirstNames", "contactLastNames", "contactTelephoneNumber", "contactEmail", "city"])
    kept, dropped = drop_personal_columns(df)
    assert list(kept.columns) == ["name", "country", "city"]
    assert len(dropped) == 9


def test_hierarchy_parents():
    assert domain_parent("/23/53/373") == "/23/53"
    assert domain_parent("/23") is None and domain_parent(None) is None
    assert programme_part_parent("HORIZON.2.5") == "HORIZON.2"
    assert programme_part_parent("HORIZON.2") == "HORIZON"
    assert programme_part_parent("HORIZON") is None
    assert programme_part_parent("H2020-EU.3.4.") == "H2020-EU.3."


@pytest.mark.parametrize("code, family", [
    ("HORIZON-RIA", "Research and innovation action"), ("HORIZON-JU-RIA", "Research and innovation action"),
    ("HORIZON-IA", "Innovation action"), ("CS2-IA", "Innovation action"), ("HORIZON-CSA", "Coordination and support action"),
    ("HORIZON-ERC-POC", "ERC frontier research"), ("MSCA-IF-EF-ST", "Marie Sklodowska-Curie"),
    ("HORIZON-EIC-ACC-BF", "EIC innovation"), ("SME-1", "SME instrument"), ("ERA-NET-Cofund", "Co-fund"),
    ("HORIZON-AG", "Other")])
def test_action_family(code, family):
    assert action_family(code) == family


# ---------- robust CSV reader -------------------------------------------------------------------------------------
def test_split_line_clean():
    vals, repaired = split_line('"1";"a";"b"\n', 3, None)
    assert vals == ["1", "a", "b"] and not repaired


def test_split_line_unescaped_opening_quote_and_escaped_quotes():
    # real pattern seen in project.csv: the objective starts with an unescaped quote and contains doubled quotes
    vals, repaired = split_line('"1";"";""Deep learning at a ""sweet spot"" today"\n', 3, 2)
    assert vals == ["1", "", 'Deep learning at a "sweet spot" today'] and repaired


def test_split_line_stray_separator_is_merged_into_free_text_column():
    vals, repaired = split_line('"1";"text with a ";" inside";"2026-01-01"\n', 3, 1)
    assert vals == ["1", 'text with a ";" inside', "2026-01-01"] and repaired


def test_split_line_too_few_fields_is_rejected():
    with pytest.raises(ValueError):
        split_line('"1";"a"\n', 3, 1)
