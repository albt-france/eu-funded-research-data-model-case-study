"""Render the Mermaid diagrams (model/diagrams/*.mmd) to SVG and PNG with mermaid-cli, using the local Edge browser.
The .mmd files are the source of truth (GitHub renders them in Markdown); the images are for the PDF.
Setup once: cd .tools && npm install @mermaid-js/mermaid-cli@11.4.2   (PUPPETEER_SKIP_DOWNLOAD=1, no browser download)
Usage: python src/build_diagrams.py
"""
import json
import subprocess

from config import ROOT, TMP

DIAG = ROOT / "model" / "diagrams"
MMDC = ROOT / ".tools" / "node_modules" / ".bin" / "mmdc.cmd"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
THEME = {"theme": "base", "themeVariables": {
    "fontFamily": "Segoe UI, sans-serif", "fontSize": "18px", "primaryColor": "#EEF5FD", "primaryBorderColor": "#2A78D6",
    "primaryTextColor": "#0B0B0B", "lineColor": "#52514E", "secondaryColor": "#F4F4F2", "tertiaryColor": "#FCFCFB"},
    "er": {"layoutDirection": "TB"}, "flowchart": {"curve": "basis"}}


def main():
    TMP.mkdir(exist_ok=True)
    pcfg, cfg = TMP / "puppeteer.json", TMP / "mermaid.json"
    pcfg.write_text(json.dumps({"executablePath": EDGE, "args": ["--no-sandbox"]}), encoding="utf-8")
    cfg.write_text(json.dumps(THEME), encoding="utf-8")
    for src in sorted(DIAG.glob("*.mmd")):
        for ext, extra in (("svg", []), ("png", ["-s", "2"])):
            out = DIAG / f"{src.stem}.{ext}"
            subprocess.run([str(MMDC), "-i", str(src), "-o", str(out), "-p", str(pcfg), "-c", str(cfg), "-b", "white", *extra],
                           check=True, capture_output=True, timeout=180, shell=False)
        print("rendered", src.stem)
    write_page()


TITLES = {"01_use_cases": "Use case diagram (UML)", "02_activity_lifecycle": "Activity diagram: life cycle of a grant (UML)",
          "03_conceptual": "Conceptual model", "04_logical_er": "Logical model: entity-relationship diagram",
          "05_class_uml": "Class diagram (UML)", "06_sequence_load": "Sequence diagram: loading a CORDIS release (UML)",
          "07_star_schema": "Analytical variant: star schema"}


def write_page():
    """model/DIAGRAMS.md: every diagram as a Mermaid block (GitHub renders them) with a link to its source and image."""
    out = ["# Diagrams", "", "Diagrams as code: the `.mmd` files are the source; GitHub renders the blocks below; "
           "`python src/build_diagrams.py` renders SVG and PNG for the report.", ""]
    for src in sorted(DIAG.glob("*.mmd")):
        body = "\n".join(line for line in src.read_text(encoding="utf-8").splitlines() if not line.startswith("%%"))
        out += [f"## {TITLES.get(src.stem, src.stem)}", "", f"Source: [`diagrams/{src.name}`](diagrams/{src.name}) · "
                f"image: [`{src.stem}.svg`](diagrams/{src.stem}.svg)", "", "```mermaid", body, "```", ""]
    (DIAG.parent / "DIAGRAMS.md").write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    import sys
    write_page() if "--page-only" in sys.argv else main()
