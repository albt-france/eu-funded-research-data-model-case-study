"""Robust reader for the CORDIS CSV exports.

Profiling finding: the files are ';'-separated, every field is quoted, one record per line, but some free-text fields
(e.g. the project objective) start or contain quotes that are not escaped. Strict CSV parsers (DuckDB, pandas C engine)
stop on those lines. This reader splits each line on the '";"' separator and, when a line has too many fields, merges the
extra pieces back into the one free-text column that can hold them. Every repaired line is counted for the profile.
"""
from pathlib import Path

import pandas as pd

# column that can absorb stray separators, per file (the long free-text field)
FREE_TEXT = {"project.csv": "objective", "organization.csv": "name", "topics.csv": "title",
             "euroSciVoc.csv": "euroSciVocDescription", "legalBasis.csv": "title", "webLink.csv": "physUrl",
             "webItem.csv": "title", "policyPriorities.csv": None}


def split_line(line: str, n_fields: int, free_idx: int | None) -> tuple[list[str], bool]:
    """Split one CORDIS line into exactly n_fields values. Returns (values, repaired)."""
    s = line.rstrip("\r\n")
    if s.startswith('"'):
        s = s[1:]
    if s.endswith('"'):
        s = s[:-1]
    parts = s.split('";"')
    repaired = False
    if len(parts) != n_fields:
        if free_idx is None or len(parts) < n_fields:
            raise ValueError(f"expected {n_fields} fields, got {len(parts)}")
        extra = len(parts) - n_fields
        parts = parts[:free_idx] + ['";"'.join(parts[free_idx:free_idx + extra + 1])] + parts[free_idx + extra + 1:]
        repaired = True
    vals = []
    for v in parts:
        v = v.replace('""', '"')                       # escaped quote -> quote
        if v.startswith('"') and v.count('"') % 2 == 1:  # unbalanced opening quote left by a bad export
            v, repaired = v[1:], True
        vals.append(v)
    return vals, repaired


def read_cordis(path: Path) -> tuple[pd.DataFrame, dict]:
    """Read one CORDIS CSV as strings. Empty strings become missing values. Returns (frame, parse stats)."""
    path = Path(path)
    with open(path, encoding="utf-8-sig") as fh:
        header = fh.readline().rstrip("\r\n")
        cols = [c.strip('"') for c in header.split(";")]
        free = FREE_TEXT.get(path.name)
        free_idx = cols.index(free) if free in cols else None
        rows, repaired, rejected = [], 0, 0
        for line in fh:
            if not line.strip():
                continue
            try:
                vals, rep = split_line(line, len(cols), free_idx)
            except ValueError:
                rejected += 1
                continue
            repaired += rep
            rows.append(vals)
    df = pd.DataFrame(rows, columns=cols).replace({"": None})
    return df, {"file": path.name, "rows": len(df), "columns": len(cols), "repaired_lines": repaired, "rejected_lines": rejected}
