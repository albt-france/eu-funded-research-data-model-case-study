"""Shared paths, constants and small helpers."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"          # parquet cache of the raw files (not versioned)
PROC = ROOT / "data" / "processed"           # small analysis outputs (versioned)
REF = ROOT / "data" / "reference"            # EU Vocabularies extracts (versioned)
DB = ROOT / "data" / "cordis.duckdb"         # the relational database (not versioned, rebuilt by src/load.py)
DDL = ROOT / "model" / "ddl" / "schema.sql"
MART = ROOT / "model" / "ddl" / "mart.sql"
DOCS = ROOT / "docs"
IMG = DOCS / "img"
SEM = ROOT / "semantic"
TMP = ROOT / ".tmp"

PROGRAMMES = {
    "HORIZON": {"folder": "horizon", "name": "Horizon Europe", "start": 2021, "end": 2027,
                "legal_act": "Regulation (EU) 2021/695", "url": "https://eur-lex.europa.eu/eli/reg/2021/695/oj"},
    "H2020": {"folder": "h2020", "name": "Horizon 2020", "start": 2014, "end": 2020,
              "legal_act": "Regulation (EU) No 1291/2013", "url": "https://eur-lex.europa.eu/eli/reg/2013/1291/oj"},
}
EU27 = ["AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT",
        "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"]
ORG_TYPES = {"HES": "Higher or secondary education establishment", "REC": "Research organisation",
             "PRC": "Private for-profit entity (excluding education)", "PUB": "Public body (excluding research and education)",
             "OTH": "Other"}
ROLES = ["coordinator", "participant", "partner", "thirdParty", "internationalPartner"]

FOOTER = "Independent case study based on EU open data · not affiliated with any organisation mentioned in the job posting"


def _ai_note() -> str:
    """The AI-use statement is written once, in the README (Methods); the report reads it from there."""
    for line in (ROOT / "README.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("AI-assisted workflow:"):
            return line.strip()
    return ""


AI_NOTE = _ai_note()
DATA_DATE = "16 Nov 2026"   # CORDIS bundles downloaded on this date (see data/raw/download_log.csv)
