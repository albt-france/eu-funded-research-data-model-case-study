"""Staging: read the raw CORDIS files once with the robust reader, drop personal columns, cache as parquet.

Usage: python src/stage.py [--raw-dir data/raw] -> data/interim/<programme>_<file>.parquet + data/interim/parse_stats.csv
"""
import sys

import pandas as pd

from clean import drop_personal_columns
from config import INTERIM, PROGRAMMES, RAW
from cordis_io import read_cordis

FILES = ["project", "organization", "euroSciVoc", "topics", "legalBasis", "webLink"]


def stage(raw_dir=RAW, out_dir=INTERIM, programmes=None) -> pd.DataFrame:
    out_dir.mkdir(parents=True, exist_ok=True)
    stats = []
    for prog, meta in PROGRAMMES.items():
        if programmes and prog not in programmes:
            continue
        folder = raw_dir / meta["folder"]
        if not folder.exists():
            print(f"{prog}: no raw folder {folder}, skipped")
            continue
        for f in FILES:
            src = folder / f"{f}.csv"
            if not src.exists():
                continue
            df, st = read_cordis(src)
            df, dropped = drop_personal_columns(df)
            df.to_parquet(out_dir / f"{prog}_{f}.parquet", index=False)
            stats.append({"programme": prog, **st, "dropped_personal_columns": ";".join(dropped)})
    s = pd.DataFrame(stats)
    s.to_csv(out_dir / "parse_stats.csv", index=False)
    return s


def read(prog: str, name: str, base=INTERIM) -> pd.DataFrame:
    p = base / f"{prog}_{name}.parquet"
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()


if __name__ == "__main__":
    raw = RAW
    if "--raw-dir" in sys.argv:
        from pathlib import Path
        raw = Path(sys.argv[sys.argv.index("--raw-dir") + 1])
    print(stage(raw).to_string(index=False))
