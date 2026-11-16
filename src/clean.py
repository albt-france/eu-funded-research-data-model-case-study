"""Cleaning rules, as small pure functions (each one is unit-tested in tests/test_clean.py)."""
import re
import unicodedata

import pandas as pd

# CORDIS uses EU interinstitutional codes; the model stores ISO 3166-1 alpha-2
COUNTRY_FIX = {"EL": "GR", "UK": "GB"}

# columns dropped at ingestion: personal data or address-level detail that is not needed for the analysis
# (older CORDIS exports carried contact persons; the rule is kept generic so that such columns never get through)
PERSONAL_PATTERNS = re.compile(r"(contact|firstname|lastname|telephone|phone|fax|email|street|postcode|geolocation|vatnumber)",
                               re.I)
LEGAL_FORMS = r"\b(GMBH|AG|SA|SAS|SARL|SRL|SL|SLU|SPA|BV|NV|LTD|LIMITED|PLC|AB|AS|OY|OU|KFT|SP ZOO|EV|E V|VZW|ASBL|INC|LLC)\b"


def parse_amount(x) -> float | None:
    """'2073781,25' or '2073781.25' -> 2073781.25 ; '' / None -> None. CORDIS mixes both decimal separators."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip().replace(" ", "").replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:          # '1.234,56' (thousands '.') or '1,234.56' (thousands ',')
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_date(x) -> pd.Timestamp | None:
    """ISO date or datetime string -> date; anything unparseable -> None."""
    if x is None or (isinstance(x, float) and pd.isna(x)) or str(x).strip() == "":
        return None
    d = pd.to_datetime(str(x).strip()[:10], format="%Y-%m-%d", errors="coerce")
    return None if pd.isna(d) else d


def to_bool(x) -> bool | None:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip().lower()
    return True if s in ("true", "1", "yes") else False if s in ("false", "0", "no") else None


def country_iso2(code) -> str | None:
    """CORDIS country code -> ISO 3166-1 alpha-2 (EL -> GR, UK -> GB); empty -> None."""
    if code is None or (isinstance(code, float) and pd.isna(code)):
        return None
    c = str(code).strip().upper()
    if not c:
        return None
    return COUNTRY_FIX.get(c, c)


def normalise_name(name) -> str | None:
    """Matching key for organisation names: upper case, no accents, no punctuation, no legal form, single spaces."""
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return None
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9 ]+", " ", s.upper())
    s = re.sub(LEGAL_FORMS, " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def drop_personal_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Remove columns that can hold personal data or address detail. Returns (frame, dropped column names)."""
    dropped = [c for c in df.columns if PERSONAL_PATTERNS.search(c.replace("_", ""))]
    return df.drop(columns=dropped), dropped


def domain_parent(code: str | None) -> str | None:
    """EuroSciVoc path code '/23/53/373' -> parent '/23/53' ; top level '/23' -> None."""
    if not code or code.count("/") <= 1:
        return None
    return code.rsplit("/", 1)[0]


def programme_part_parent(code: str | None) -> str | None:
    """Legal-basis code -> parent code. 'HORIZON.2.5' -> 'HORIZON.2' ; 'H2020-EU.3.4.' -> 'H2020-EU.3.' ; root -> None."""
    if not code:
        return None
    c = code.rstrip(".")
    trail = "." if code.endswith(".") else ""
    if "." not in c:
        return None
    parent = c.rsplit(".", 1)[0]
    return parent + trail if "." in parent or trail else parent
