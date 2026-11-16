"""Download the official EU open data used in this study (low frequency, one request per file).

PUBLIC DATA:
- CORDIS - EU research projects under Horizon Europe (2021-2027), CSV bundle, Publications Office of the EU.
- CORDIS - H2020 projects (2014-2020), CSV bundle (optional, --h2020), to compare two programmes.
- EuroSciVoc taxonomy (SKOS), queried from the Publications Office SPARQL endpoint (see src/sparql_endpoint.py).

Raw files go to data/raw/ (not versioned). Each download is logged in data/raw/download_log.csv with its date and size.
Usage: python src/download.py [--h2020]
"""
import csv
import datetime as dt
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SOURCES = {
    "horizon": "https://cordis.europa.eu/data/cordis-HORIZONprojects-csv.zip",
    "h2020": "https://cordis.europa.eu/data/cordis-h2020projects-csv.zip",
}
UA = {"User-Agent": "eu-open-data-case-study/1.0 (research; low frequency)"}


def fetch(name: str, url: str) -> Path:
    target = RAW / Path(url).name
    if target.exists() and target.stat().st_size > 1_000_000:
        print(f"{target.name}: already downloaded ({target.stat().st_size / 1e6:.1f} MB)")
        return target
    print(f"Downloading {url} ...")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=600) as r, open(target, "wb") as fh:
        while chunk := r.read(1 << 20):
            fh.write(chunk)
    log = RAW / "download_log.csv"
    new = not log.exists()
    with open(log, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["source", "url", "downloaded_utc", "bytes"])
        w.writerow([name, url, dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), target.stat().st_size])
    return target


def extract(zip_path: Path, folder: str) -> Path:
    out = RAW / folder
    out.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        for m in z.namelist():
            name = Path(m).name
            if name.endswith((".csv", ".xlsx", ".json")) and not (out / name).exists():
                (out / name).write_bytes(z.read(m))
    return out


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    wanted = ["horizon"] + (["h2020"] if "--h2020" in sys.argv else [])
    for name in wanted:
        z = fetch(name, SOURCES[name])
        out = extract(z, name)
        print(f"{name}: {len(list(out.iterdir()))} files in {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
