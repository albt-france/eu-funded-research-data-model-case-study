"""Report style and helpers: colours, matplotlib theme, inline SVG, HTML -> PDF / PNG with headless Edge."""
import io
import re
import shutil
import subprocess
import time
from pathlib import Path

from config import TMP

BLUE, BLUE_L, BLUE_D = "#2A78D6", "#86B6EF", "#1C5CAB"
GRAY, GRAY_D, RED, GREEN = "#C9C7BF", "#898781", "#D03B3B", "#1BAF7A"
INK, INK2, GRID, CARD, BG = "#0B0B0B", "#52514E", "#E1E0D9", "#FCFCFB", "#F4F4F2"


def pct(x, d=0):
    return f"{100 * x:.{d}f}%"


def edge() -> str:
    for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
        if Path(p).exists():
            return p
    return shutil.which("msedge") or "msedge"


def wait_file(path: Path, timeout=90):
    last, t0 = -1, time.time()
    while time.time() - t0 < timeout:
        if path.exists() and path.stat().st_size > 0 and path.stat().st_size == last:
            return
        last = path.stat().st_size if path.exists() else -1
        time.sleep(1.0)
    raise TimeoutError(f"{path} not produced")


def html_to_pdf(html_file: Path, pdf: Path, title: str):
    prof = TMP / "edge-profile"
    pdf.unlink(missing_ok=True)
    subprocess.run([edge(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--print-to-pdf-no-header",
                    f"--user-data-dir={prof}", f"--print-to-pdf={pdf}", html_file.as_uri()], check=True, capture_output=True, timeout=180)
    wait_file(pdf)
    clean_pdf(pdf, title)


def screenshot(html_file: Path, png: Path, w: int, h: int):
    prof = TMP / "edge-profile"
    png.unlink(missing_ok=True)
    subprocess.run([edge(), "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={prof}",
                    f"--window-size={w},{h}", f"--screenshot={png}", html_file.as_uri()], check=True, capture_output=True, timeout=120)
    wait_file(png)


def clean_pdf(path: Path, title: str):
    """Metadata reduced to the title: no author, tool or path."""
    from pypdf import PdfReader, PdfWriter
    r, w = PdfReader(str(path)), PdfWriter()
    for pg in r.pages:
        w.add_page(pg)
    w.add_metadata({"/Title": title})
    for k in ("/Producer", "/Creator", "/Author"):
        w._info.get_object().pop(k, None)
    tmp = path.with_suffix(".tmp.pdf")
    with open(tmp, "wb") as fh:
        w.write(fh)
    tmp.replace(path)


def mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 9.5, "text.color": INK2,
        "axes.edgecolor": GRID, "axes.labelcolor": INK2, "axes.facecolor": CARD, "figure.facecolor": CARD,
        "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
        "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.8,
        "xtick.color": GRAY_D, "ytick.color": INK2, "xtick.labelsize": 9, "ytick.labelsize": 9,
        "xtick.major.size": 0, "ytick.major.size": 0, "legend.frameon": False, "legend.fontsize": 9,
        "svg.fonttype": "none", "axes.axisbelow": True})
    return plt


def svg(f) -> str:
    import matplotlib.pyplot as plt
    buf = io.StringIO()
    f.savefig(buf, format="svg", bbox_inches="tight", pad_inches=0.05)
    plt.close(f)
    s = buf.getvalue()
    s = s[s.find("<svg"):]
    s = re.sub(r'width="[\d.]+pt" height="[\d.]+pt"', 'width="100%" height="100%" preserveAspectRatio="xMidYMid meet"', s, 1)
    return re.sub(r"<metadata>.*?</metadata>", "", s, flags=re.S)
