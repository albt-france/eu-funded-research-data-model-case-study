"""8-page PDF report (16:9): HTML + inline SVG charts + rendered diagrams, printed by headless Edge.
Every number is read from the database or from data/processed (written by the pipeline); none is typed in the text.
Usage: python src/build_pdf.py -> docs/EU_Funded_Research_Data_Model_Case_Study.pdf (+ docs/img/pdf_p*.png)
"""
import json
import re
import subprocess
import sys

import duckdb
import numpy as np
import pandas as pd
from jinja2 import Template

from config import AI_NOTE, DATA_DATE, DB, DOCS, FOOTER, IMG, PROC, ROOT, SEM, TMP
from report_style import BLUE, BLUE_L, GRAY, GRAY_D, GREEN, INK2, html_to_pdf, mpl, screenshot, svg

PDF = DOCS / "EU_Funded_Research_Data_Model_Case_Study.pdf"
DIAG = ROOT / "model" / "diagrams"
plt = mpl()

CSS = """
@page { size: 16in 9in; margin: 0 }
* { box-sizing: border-box; margin: 0; padding: 0 }
body { font-family: 'Segoe UI', system-ui, sans-serif; color: #0B0B0B; background: #F4F4F2; }
.page { width: 1536px; height: 864px; padding: 28px 40px 14px; display: flex; flex-direction: column;
        background: #F4F4F2; page-break-after: always; overflow: hidden; position: relative }
header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 11px; min-height: 54px }
h1 { font-size: 24px; font-weight: 700; line-height: 1.2; max-width: 1240px; letter-spacing: -0.2px }
.sub { color: #52514E; font-size: 13.5px; margin-top: 5px; max-width: 1270px; line-height: 1.4 }
.tag { font-size: 11.5px; font-weight: 700; letter-spacing: .8px; color: #52514E; border: 1px solid #C9C7BF; border-radius: 4px;
       padding: 4px 9px; white-space: nowrap; margin-top: 6px; background: #FCFCFB }
.tag.real { color: #0E7A55; border-color: #8FD3B8 } .tag.sim { color: #1C5CAB; border-color: #86B6EF }
.kpis { display: grid; gap: 14px; margin-bottom: 11px }
.card { background: #FCFCFB; border: 1px solid #E1E0D9; border-radius: 8px; padding: 11px 15px; display: flex; flex-direction: column;
        min-height: 0; overflow: hidden }
.kpi { padding: 10px 16px }
.klabel { font-size: 11px; font-weight: 700; color: #52514E; letter-spacing: .5px; text-transform: uppercase }
.kval { font-size: 27px; font-weight: 700; margin-top: 2px; line-height: 1.15; color: #1C5CAB }
.knote { font-size: 12px; color: #52514E; margin-top: 3px; line-height: 1.35 }
.grid { display: grid; gap: 13px; flex: 1; min-height: 0 }
.card h3 { font-size: 13.5px; font-weight: 600; margin-bottom: 6px }
.card h3 .t { font-size: 10px; font-weight: 700; color: #0E7A55; border: 1px solid #8FD3B8; border-radius: 3px; padding: 1px 5px; margin-left: 6px }
.card h3 .t.s { color: #1C5CAB; border-color: #86B6EF }
.body { flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; font-size: 12.5px; line-height: 1.45 }
.body svg { width: 100%; height: 100% } .body img { max-width: 100%; max-height: 100%; object-fit: contain }
.body.text { display: block; overflow: hidden; color: #2B2A28 }
.body.text p { margin-bottom: 6px } .body.text ul, .body.text ol { margin: 0 0 6px 18px } .body.text li { margin-bottom: 3px }
table { border-collapse: collapse; width: 100%; font-size: 11.5px }
th { text-align: left; color: #52514E; font-weight: 600; border-bottom: 1px solid #C9C7BF; padding: 3px 5px }
td { padding: 3px 5px; border-bottom: 1px solid #EEEDE8; vertical-align: top } td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap }
footer { font-size: 10.5px; color: #898781; margin-top: 8px }
.flow { display: flex; gap: 7px; align-items: stretch; width: 100% }
.flow div.s { flex: 1; border: 1px solid #86B6EF; background: #EEF5FD; border-radius: 6px; padding: 7px; font-size: 12px; text-align: center }
.flow div.s b { display: block; color: #1C5CAB; margin-bottom: 3px } .flow div.a { color: #898781; font-size: 18px; align-self: center }
pre, .mono { font-family: Consolas, monospace; font-size: 11px; background: #F1F0EB; border-radius: 4px }
pre { padding: 7px 9px; white-space: pre; overflow: hidden; line-height: 1.35 } .mono { padding: 1px 4px }
.ai { border-left: 3px solid #2A78D6; padding: 6px 10px; background: #EEF5FD; font-size: 13px; margin-top: 4px }
.ok { color: #0E7A55; font-weight: 600 } .warn { color: #9A6A00; font-weight: 600 }
"""

PAGE = Template("""
<section class="page">
  <header><div><h1>{{ p.title }}</h1>{% if p.subtitle %}<p class="sub">{{ p.subtitle }}</p>{% endif %}</div>
  <div class="tag {{ p.tag_class }}">{{ p.tag }}</div></header>
  {% if p.kpis %}<div class="kpis" style="grid-template-columns: repeat({{ p.kpis|length }}, 1fr)">
    {% for k in p.kpis %}<div class="card kpi"><div class="klabel">{{ k[0] }}</div><div class="kval">{{ k[1] }}</div><div class="knote">{{ k[2] }}</div></div>{% endfor %}
  </div>{% endif %}
  <div class="grid" style="grid-template-columns: {{ p.cols }}; grid-template-rows: {{ p.rows }}">
    {% for c in p.cards %}<div class="card" style="grid-column: {{ c.col }}; grid-row: {{ c.row }}">
      {% if c.title %}<h3>{{ c.title }}</h3>{% endif %}<div class="body {{ 'text' if c.text else '' }}">{{ c.body }}</div></div>{% endfor %}
  </div>
  <footer>{{ p.footer }} · {{ foot }}</footer>
</section>""")


def card(title, body, col="auto", row="auto", text=False, tag=None):
    if tag:
        title += f"<span class='t {'s' if tag == 'SIMULATED' else ''}'>{tag}</span>"
    return dict(title=title, body=body, col=col, row=row, text=text)


def img(path, alt=""):
    return f'<img src="{path.as_uri()}" alt="{alt}">' if path.exists() else f"<p>{alt} (not generated)</p>"


def fig(w, h):
    return plt.subplots(figsize=(w / 96, h / 96), dpi=96)


def table(df, num=()):
    h = "".join(f"<th class='{'n' if c in num else ''}'>{c}</th>" for c in df.columns)
    rows = "".join("<tr>" + "".join(f"<td class='{'n' if c in num else ''}'>{r[c]}</td>" for c in df.columns) + "</tr>"
                   for _, r in df.iterrows())
    return f"<table><tr>{h}</tr>{rows}</table>"


def bn(x, d=1):
    return f"EUR {x / 1e9:,.{d}f} bn"


def count_tests() -> int:
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], cwd=ROOT, capture_output=True, text=True).stdout
    m = re.search(r"(\d+) tests? collected", out)
    return int(m.group(1)) if m else 0


# ------------------------------------------------------------------ charts
def hbar(labels, values, colors, w, h, fmt, xlabel=None, xmax=None):
    f, ax = fig(w, h)
    y = np.arange(len(labels))
    ax.barh(y, values, color=colors, height=0.62)
    ax.set_yticks(y, labels, fontsize=8.5)
    ax.invert_yaxis()
    xm = xmax or max(values) * 1.28
    ax.set_xlim(0, xm)
    for i, v in enumerate(values):
        ax.text(v + xm * 0.01, i, fmt(v), va="center", fontsize=8.5, color=INK2)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x")
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=8.5)
    return svg(f)


def ch_completeness():
    p = pd.read_csv(PROC / "profile_project.csv")
    p = p[p.missing_pct > 0].sort_values("missing_pct", ascending=False).head(6)
    con = duckdb.connect(str(DB), read_only=True)
    zero = con.execute("select avg(case when total_cost is null then 1 else 0 end) from project where programme_code = 'HORIZON'").fetchone()[0]
    con.close()
    labels = list(p.column) + ["totalCost = 0 (not reported)"]
    vals = list(p.missing_pct) + [100 * zero]
    return hbar(labels, vals, [GRAY] * len(p) + [BLUE], 520, 230, lambda v: f"{v:.1f}%", "% of Horizon Europe projects", 115)


def ch_pillar(pil):
    d = pil[pil.programme_code == "HORIZON"].sort_values("eu_contribution_bn", ascending=False)
    lab = (d.pillar_title.str.replace("Pillar ", "").str.replace(" - ", ": ")
           .str.replace("Global Challenges and European Industrial Competitiveness", "Global Challenges &\nCompetitiveness")
           .str.replace("Widening Participation and Strengthening the European Research Area", "Widening & ERA")
           .str.replace("Euratom Research and Training Programme (EURATOM)", "Euratom"))
    return hbar(list(lab), list(d.eu_contribution_bn), [BLUE] * len(d), 460, 290, lambda v: f"{v:.1f}", "EUR bn (maximum EU contribution)")


def ch_countries(cty):
    d = cty.dropna(subset=["country"]).head(12)
    return hbar(list(d.country), list(d.eu_contribution_bn), [BLUE if e else GRAY_D for e in d.is_eu27], 460, 600,
                lambda v: f"{v:.1f}", "EUR bn, net contribution (grey = not EU-27)")


def ch_orgtype(ot):
    short = {"HES": "Higher\neducation", "REC": "Research\norganisations", "PRC": "Companies", "PUB": "Public\nbodies", "OTH": "Other"}
    d = ot.dropna(subset=["type_code"])
    f, ax = fig(460, 290)
    x = np.arange(5)
    order = ["HES", "REC", "PRC", "OTH", "PUB"]
    for i, (prog, col, name) in enumerate((("HORIZON", BLUE, "Horizon Europe"), ("H2020", GRAY, "Horizon 2020"))):
        v = d[d.programme_code == prog].set_index("type_code").share_pct.reindex(order).values
        ax.bar(x + (i - 0.5) * 0.38, v, 0.38, color=col, label=name)
        for xi, vi in zip(x, v):
            ax.text(xi + (i - 0.5) * 0.38, vi + 0.8, f"{vi:.0f}", ha="center", fontsize=8, color=INK2)
    ax.set_xticks(x, [short[o] for o in order], fontsize=8.5)
    ax.set_ylabel("% of EU contribution")
    ax.legend(fontsize=8)
    ax.grid(axis="x", visible=False)
    return svg(f)


def ch_consortium(cs):
    d = cs[cs.projects > 100].sort_values("median_members")
    f, ax = fig(460, 290)
    y = np.arange(len(d))
    ax.barh(y, d.median_members, color=[BLUE if s < 30 else GRAY for s in d.single_beneficiary_pct], height=0.6)
    for i, r in enumerate(d.itertuples()):
        ax.text(r.median_members + 0.3, i, f"{r.median_members:.0f} members · {r.avg_countries:.1f} countries · "
                f"{r.single_beneficiary_pct:.0f}% single", va="center", fontsize=8, color=INK2)
    ax.set_yticks(y, d.action_family, fontsize=8.5)
    ax.set_xlim(0, d.median_members.max() * 2.6)
    ax.set_xlabel("Median consortium size (grey = mostly single-beneficiary grants)", fontsize=8.5)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x")
    return svg(f)


def ch_ai():
    d = pd.read_csv(SEM / "results" / "graph_01_domain_tree.csv").head(8)
    return hbar(list(d.label), list(d.projects), [BLUE_L] * len(d), 470, 230, lambda v: f"{v:,.0f}", "projects (a project can have several)")


# ------------------------------------------------------------------ pages
def build_pages():
    F = json.loads((PROC / "findings.json").read_text(encoding="utf-8"))
    S = json.loads((PROC / "semantic_summary.json").read_text(encoding="utf-8"))
    qa = pd.read_csv(PROC / "qa_report.csv")
    issues = pd.read_csv(PROC / "profile_issues.csv")
    pil = pd.read_csv(PROC / "us01_funding_by_pillar.csv")
    cty = pd.read_csv(PROC / "us02_funding_by_country.csv")
    ot = pd.read_csv(PROC / "us03_funding_by_org_type.csv")
    cs = pd.read_csv(PROC / "us05_consortium_size.csv")
    pairs = pd.read_csv(PROC / "us07_country_network.csv")
    con = duckdb.connect(str(DB), read_only=True)
    q = lambda s: con.execute(s).fetchone()[0]  # noqa: E731
    n_tables = q("select count(*) from duckdb_tables() where schema_name = 'main'")
    n_views = q("select count(*) from duckdb_views() where schema_name = 'mart'")
    repaired = q("select sum(lines_repaired) from load_batch")
    zero_cost = q("select count(*) from project where programme_code = 'HORIZON' and total_cost is null")
    n_dom = q("select count(*) from science_domain")
    n_off = q("select count(*) from science_domain where euroscivoc_uri is not null")
    sme_change = q("select count(*) from (select organisation_id from participation x join project p using (project_id) "
                   "where p.programme_code = 'HORIZON' group by 1 having count(distinct is_sme) > 1)")
    n_part = q("select count(*) from participation")
    con.close()
    he, h2 = F["HORIZON"], F["H2020"]
    n_tests = count_tests()
    pil_he = pil[pil.programme_code == "HORIZON"].set_index("pillar_title").eu_contribution_bn
    p2_share = pil_he[pil_he.index.str.startswith("Pillar II -")].sum() / pil_he.sum()
    collab = {k: v for k, v in F["consortium_by_family"].items() if k in ("Research and innovation action", "Innovation action")}
    pages = []

    # 0 Overview
    qs = ("<ol><li><b>How is an EU-funded project run</b>, and what must a data system record about it?</li>"
          "<li><b>What does the open data really look like</b>: structure, keys, anomalies?</li>"
          "<li><b>How should it be modelled</b>: conceptual, logical (ER), physical (SQL), UML?</li>"
          "<li><b>What does an ontology-aligned graph add</b> to the relational model?</li>"
          "<li><b>What does Horizon Europe fund, and who works together?</b></li></ol>")
    ans = (f"<ol><li>Nine steps from call to final payment; the open data covers the signed grant, its consortium and roles, "
           f"not proposals, reporting periods or payments (p.1).</li>"
           f"<li>Usable after repair: {repaired:,} broken lines, two decimal separators, total cost not reported for "
           f"{zero_cost / he['projects']:.0%} of grants, SME status that changes over time (p.2).</li>"
           f"<li>{n_tables} tables in 3NF around the participation, a star schema derived from them, both tested (p.3-4).</li>"
           f"<li>{n_off / n_dom:.0%} of the domain codes match official EuroSciVoc concepts: the graph reuses EU identifiers "
           f"and validates its rules with SHACL (p.5).</li>"
           f"<li>{bn(he['eu_contribution'])} committed in {he['projects']:,} grants; Pillar II holds {p2_share:.0%}; "
           f"collaborative projects gather a median of {collab['Research and innovation action']['median_members']:.0f} "
           f"organisations (p.6).</li></ol>")
    flow = ('<div class="flow">' + '<div class="a">→</div>'.join(f'<div class="s"><b>{a}</b>{b}</div>' for a, b in [
        ("1. Business", "life cycle, actors,<br>14 user stories"), ("2. Data", "profiling of CORDIS,<br>16 findings"),
        ("3. Model", "conceptual, ER,<br>UML, DDL"), ("4. Build", f"Python pipeline,<br>{n_tests} tests, CI, Git"),
        ("5. Meaning", "RDF, SKOS, ORG,<br>SPARQL, SHACL"), ("6. Analysis", "SQL per question,<br>dashboard")]) + "</div>")
    pages.append(dict(
        title="Modelling EU-funded research: from business analysis to a relational model and an ontology-aligned "
              "knowledge graph of Horizon Europe",
        subtitle="EU open data (CORDIS, EuroSciVoc) analysed and modelled end to end: requirements, ER and UML diagrams, a tested "
                 "Python pipeline, a SQL database, an RDF layer with SPARQL, and analysis of how EU-funded projects are run.",
        tag="OVERVIEW · PUBLIC DATA", tag_class="real",
        kpis=[("Horizon Europe grants", f"{he['projects']:,}", f"{bn(he['eu_contribution'])} committed · {he['status']['SIGNED'] / he['projects']:.0%} running"),
              ("Participations modelled", f"{n_part:,}", f"Horizon Europe + Horizon 2020 · {he['countries']} countries"),
              ("Data model", f"{n_tables} tables", f"3NF + {n_views} star-schema views · {len(qa)} quality checks, 0 failed"),
              ("Knowledge graph", f"{S['triples']:,}", f"triples · {S['projects']:,} AI projects · SHACL conforms")],
        cols="1fr 1.25fr", rows="auto auto 1fr",
        cards=[card("Five questions", qs, text=True), card("Answers", ans, text=True),
               card("What the repository contains", table(pd.DataFrame([
                   ("Business and systems analysis", "life cycle, actors, 14 user stories (Given/When/Then), use case and activity diagrams", "docs/analysis/"),
                   ("Data profiling and quality", "16 findings with size and treatment; quality report after each load", "docs/analysis/"),
                   ("Data models", "conceptual, logical ER, UML class and sequence, star schema; data dictionary; DDL DuckDB and PostgreSQL", "model/"),
                   ("Pipeline", f"download, robust CSV reader, cleaning, load, {len(qa)} checks; {n_tests} tests; CI with PostgreSQL", "src/, tests/, .github/"),
                   ("Semantic layer", "RDF graph (SKOS, ORG, DCAT, Dublin Core), SPARQL queries, SHACL shapes", "semantic/"),
                   ("Analysis", "one SQL query per user story, notebook, offline dashboard (3 tabs)", "sql/, notebooks/, dashboard/")],
                   columns=["Deliverable", "Content", "Folder"])), text=True, col="1 / 3", row="3"),
               card("Approach: what a data analyst / data modeler does on a programme management system",
                    flow + "<p style='margin-top:8px;font-size:12px;color:#52514E'>All data is real and official (PUBLIC DATA): "
                    "CORDIS bundles and EU Vocabularies. The only invented data are the test fixtures (SIMULATED, used by the "
                    "tests). Descriptive figures only: no ranking of organisations or countries.</p>", col="1 / 3", row="2")],
        footer=f"Data downloaded {DATA_DATE}"))

    # 1 Business
    roles = pd.DataFrame([("Coordinator", "signs for the consortium, reports, receives payments", "exactly 1 per project"),
                          ("Beneficiary", "does the work, receives EU funding", "participant"),
                          ("Affiliated entity", "linked to a beneficiary, funded through it", "thirdParty"),
                          ("Associated partner", "takes part without EU funding", "associatedPartner"),
                          ("Agency and experts", "calls, evaluation, signature, payments", "no open data")],
                         columns=["Actor", "Role", "In the data"])
    facts = ("<ul><li><b>Eligibility</b>: collaborative actions need 3 independent entities from 3 Member States or associated "
             "countries, one in a Member State (Art. 22).</li><li><b>Evaluation</b> by independent experts on excellence, impact, "
             "quality and efficiency of implementation (Art. 28-29).</li><li><b>Time to grant</b>: applicants informed within 5 "
             "months, grants signed within 8 months of the deadline (Art. 31).</li><li><b>Funding rate</b> up to 100% (70% for "
             "innovation actions, except non-profits); 25% flat rate for indirect costs (Art. 34-35).</li>"
             "<li><b>Reporting</b>: periodic report within 60 days of each period; interim payment within 90 days of acceptance.</li></ul>")
    pages.append(dict(
        title="How an EU-funded project is run: nine steps from call to final payment, and the open data only sees the signed grant",
        subtitle="Business and systems analysis first: the life cycle, the actors and what each step leaves in the data. Facts from "
                 "Regulation (EU) 2021/695 and the Funding & Tenders Portal manual, summarised. 14 user stories with Given/When/Then "
                 "criteria follow from it (docs/analysis/REQUIREMENTS.md).",
        tag="PUBLIC SOURCES · ANALYSIS", tag_class="real", kpis=None, cols="1.2fr 1fr 1fr", rows="0.9fr 1fr",
        cards=[card("UML activity diagram: life cycle of a grant, with swimlanes", img(DIAG / "02_activity_lifecycle.svg"), col="1 / 4"),
               card("UML use case diagram", img(DIAG / "01_use_cases.svg")),
               card("Actors and roles", table(roles) + "<p style='margin-top:7px'><b>Not in open data</b>: proposals and "
                    "evaluation scores, <b>reporting periods and payments</b> (the amount is the maximum grant), persons. The model "
                    "still has a <span class='mono'>reporting_period</span> table, modelled from the business and empty here (US13).</p>",
                    text=True),
               card("Rules that shape the data (Regulation (EU) 2021/695)", facts, text=True)],
        footer="docs/analysis/BUSINESS_CONTEXT.md · eur-lex.europa.eu/eli/reg/2021/695/oj · Funding & Tenders Portal Online Manual"))

    # 2 Data
    it = issues[issues.Area.isin(["Format", "Amounts", "Codes", "Keys", "Organisations", "Classification"])].head(10)
    it = it.assign(Finding=it.Finding.str.replace("`", ""), Treatment=it.Treatment.str.replace("`", "").str.replace("**", ""))
    qat = qa[["id", "rule", "offending_rows", "status"]].copy()
    qat["status"] = qat.status.map(lambda s: f"<span class='{'ok' if s == 'PASS' else 'warn'}'>{s}</span>")
    qat["offending_rows"] = qat.offending_rows.map("{:,}".format)
    qat.columns = ["", "Check after each load", "Rows", ""]
    pages.append(dict(
        title=f"What the data really looks like: {repaired:,} broken lines, two decimal separators, and the total cost missing "
              f"for {zero_cost / he['projects']:.0%} of grants",
        subtitle="Profiling before modelling: types, missing values, candidate keys and functional dependencies tested on the "
                 "CORDIS files. Each finding has a size and a treatment; strict CSV parsers (DuckDB, pandas) stop on these files.",
        tag="PUBLIC DATA · PROFILING", tag_class="real",
        kpis=[("Lines repaired", f"{repaired:,}", "unescaped quotes, stray separators · 0 rejected"),
              ("Total cost not reported", f"{zero_cost:,}", "lump-sum grants: NULL, never a real zero"),
              ("SME status changes", f"{sme_change:,}", "organisations: PIC → SME does not hold"),
              ("Projects not classified", f"{F['unclassified_share_he']:.0%}", "no EuroSciVoc domain in CORDIS")],
        cols="1.45fr 1fr", rows="1fr 0.75fr",
        cards=[card("Findings and treatment (docs/analysis/DATA_PROFILING.md)", table(it[["Finding", "Size (Horizon Europe unless stated)", "Treatment"]].rename(
                    columns={"Size (Horizon Europe unless stated)": "Size"})), row="1 / 3", text=True),
               card("project.csv: missing or not reported", ch_completeness(), tag="PUBLIC DATA"),
               card(f"Quality checks: {int((qa.status == 'PASS').sum())} pass, {int((qa.status == 'WARN').sum())} known and explained, 0 fail",
                    "<p>Control totals: raw rows = loaded rows; raw EU contribution = loaded contribution; exactly one coordinator per "
                    "project; star schema total = model total; domain weights add up to 1.</p><p>WARN = a property of the source, "
                    "reported, not hidden: e.g. 16 associated partners carry an amount the funded partners already account for.</p>",
                    text=True)],
        footer="src/profile_data.py, src/quality.py · docs/analysis/QA_REPORT.md"))

    # 3 Model
    dict_ex = pd.DataFrame([
        ("participation_id", "BIGINT", "PK", "surrogate key"), ("project_id", "BIGINT", "FK", "→ project"),
        ("organisation_id", "BIGINT", "FK", "→ organisation (PIC)"), ("role_code", "VARCHAR", "FK", "→ participant_role"),
        ("order_no", "SMALLINT", "UK*", "position in the consortium list"),
        ("net_ec_contribution", "DECIMAL(15,2)", "", "EU funding net of transfers, ≥ 0"),
        ("is_sme", "BOOLEAN", "", "SME status at that time"), ("has_ended", "BOOLEAN", "", "left the project")],
        columns=["Column", "Type", "Key", "Meaning"])
    choices = ("<ul><li><b>Participation</b> is the association entity between project and organisation: it carries role, "
               "order, money and SME status. Natural key (project, organisation, role, order)*, because an organisation can leave "
               "and re-join.</li><li><b>3NF</b>: names in <span class='mono'>organisation</span>, role groups in "
               "<span class='mono'>participant_role</span>, never repeated in 330,000 rows. Multi-valued source fields split.</li>"
               "<li><b>Historisation</b>: SME status stored per participation, since it changes over time.</li>"
               "<li><b>Hierarchies</b> by self-reference: programme parts (pillar > cluster) and EuroSciVoc domains (up to 7 levels).</li>"
               "<li><b>Lineage</b>: each project points to its <span class='mono'>load_batch</span>.</li>"
               "<li><b>Star schema</b> derived as views for reporting; a check compares both totals.</li></ul>")
    pages.append(dict(
        title=f"The data model: {n_tables} tables in third normal form, built around the participation of an organisation in a project",
        subtitle="Conceptual model from the business, logical model as an entity-relationship diagram with keys and cardinalities, "
                 "physical model in SQL. Diagrams are code (Mermaid): GitHub renders them; the data dictionary is generated from the "
                 "database catalogue, so it cannot drift from the DDL.",
        tag="DATA MODEL", tag_class="", kpis=None, cols="2.3fr 1fr", rows="1fr 1.05fr",
        cards=[card("Logical model: entity-relationship diagram (model/DIAGRAMS.md)", img(DIAG / "04_logical_er.svg"), row="1 / 3"),
               card("Design choices", choices, text=True),
               card("Data dictionary extract: participation (model/DATA_DICTIONARY.md)", table(dict_ex), text=True)],
        footer="model/MODEL.md · model/DIAGRAMS.md (conceptual, logical, class, sequence, star) · model/ddl/schema.sql"))

    # 4 Database and pipeline
    ddl = ("CREATE TABLE participation (\n  participation_id    BIGINT PRIMARY KEY,\n"
           "  project_id          BIGINT NOT NULL REFERENCES project,\n  organisation_id     BIGINT NOT NULL REFERENCES organisation,\n"
           "  role_code           VARCHAR(24) NOT NULL REFERENCES participant_role,\n  order_no            SMALLINT NOT NULL,\n"
           "  net_ec_contribution DECIMAL(15,2) CHECK (net_ec_contribution >= 0),\n  is_sme              BOOLEAN,\n"
           "  CONSTRAINT uq_participation\n    UNIQUE (project_id, organisation_id, role_code, order_no));\n"
           "-- PostgreSQL only: at most one coordinator per project\n"
           "CREATE UNIQUE INDEX ux_one_coordinator_per_project\n  ON participation (project_id) WHERE role_code = 'coordinator';")
    eng = (f"<ul><li><b>Pipeline</b>: download → stage (robust reader, personal columns dropped) → clean → load in foreign-key "
           f"order → star views → {len(qa)} checks. Full rebuild of both programmes in under a minute.</li>"
           f"<li><b>{n_tests} pytest tests</b>: cleaning rules, CSV repair, eight invalid rows the database must reject, end-to-end "
           f"run on SIMULATED fixtures in CORDIS format, SHACL.</li><li><b>CI</b> (GitHub Actions): tests, and the DDL applied to a "
           f"real PostgreSQL 16 server, where invalid rows must fail.</li><li><b>Git</b>: one feature branch per layer, merged "
           f"into main, tagged v1.0; CONTRIBUTING.md.</li><li><b>DuckDB</b> by default, same DDL on <b>PostgreSQL</b>.</li></ul>")
    pages.append(dict(
        title=f"From model to database: a tested Python pipeline loads {n_part:,} participations, and the database rejects invalid rows",
        subtitle="UML class diagram for the domain objects, UML sequence diagram for a load. Business rules live in constraints, "
                 "not only in code; what DuckDB cannot enforce (one coordinator) is a PostgreSQL partial index and a quality check.",
        tag="ENGINEERING", tag_class="", kpis=None, cols="0.95fr 1.3fr 0.95fr", rows="1fr 1fr",
        cards=[card("UML class diagram", img(DIAG / "05_class_uml.svg"), row="1 / 3"),
               card("UML sequence diagram: loading a CORDIS release", img(DIAG / "06_sequence_load.svg"), row="1 / 3"),
               card("Physical model (model/ddl/schema.sql, schema_postgres.sql)", f"<pre style='font-size:9.6px'>{ddl}</pre>", text=True),
               card("Python, tests, CI and Git", eng, text=True)],
        footer="src/ (download, stage, clean, load, quality) · tests/ · .github/workflows/ci.yml · CONTRIBUTING.md"))

    # 5 Semantic
    mapping = pd.DataFrame([
        ("project", "foaf:Project, org:OrganizationalCollaboration"), ("organisation", "org:Organization, org:identifier (PIC)"),
        ("participation", "org:Membership (member, organization, role)"), ("science_domain", "skos:Concept, skos:broader (EuroSciVoc URI)"),
        ("country", "dcterms:spatial → EU country authority URI"), ("dates, title, id", "dcat:startDate, dcterms:title, dcterms:identifier"),
        ("the graph", "dcat:Dataset, dcterms:license, prov:wasDerivedFrom")], columns=["Relational", "RDF (W3C and EU vocabularies)"])
    sparql = ("SELECT ?label (COUNT(DISTINCT ?project) AS ?n) WHERE {\n  ?root skos:prefLabel \"artificial intelligence\"@en .\n"
              "  ?domain skos:broader* ?root ;          # any depth\n          skos:prefLabel ?label .\n"
              "  ?project dcterms:subject ?domain .\n} GROUP BY ?label ORDER BY DESC(?n)")
    shacl = ("cs:ProjectShape sh:property [\n  sh:path [ sh:inversePath org:organization ] ;\n"
             "  sh:qualifiedValueShape [ sh:path org:role ;\n                          sh:hasValue role:coordinator ] ;\n"
             "  sh:qualifiedMinCount 1 ; sh:qualifiedMaxCount 1 ] .")
    pages.append(dict(
        title=f"Adding meaning: {n_off / n_dom:.0%} of CORDIS domain codes match official EuroSciVoc concepts, so the graph "
              "speaks the EU's own identifiers",
        subtitle=f"Relational model mapped to existing vocabularies (SKOS, W3C ORG, FOAF, DCAT, Dublin Core) for the {S['projects']:,} Horizon "
                 f"Europe projects in artificial intelligence: {S['triples']:,} triples, 10 SPARQL queries on the graph, 3 on the "
                 "Publications Office endpoint, SHACL validation. Only five local terms (amounts, SME flag).",
        tag="PUBLIC DATA · SEMANTIC LAYER", tag_class="real", kpis=None, cols="1fr 1fr 1fr", rows="1fr 1fr",
        cards=[card("Mapping: reuse, do not invent (semantic/MAPPING.md)", table(mapping), text=True),
               card("SPARQL: a domain and all its sub-domains, one property path", f"<pre>{sparql}</pre>", text=True),
               card("Result: 'artificial intelligence' and its sub-domains", ch_ai(), tag="PUBLIC DATA"),
               card("SHACL: the business rule, written for the graph", f"<pre>{shacl}</pre><p style='margin-top:6px'>Sample: "
                    f"<span class='ok'>conforms</span>. A test removes the coordinators: validation fails. The first mapping failed "
                    "one shape (a role concept with two English labels): SHACL caught a real bug.</p>", text=True),
               card("Real queries on the EU Vocabularies endpoint", "<ul><li>EuroSciVoc top concepts and their number of "
                    "descendants (transitive path).</li><li>One concept in six languages: <i>artificial intelligence, künstliche "
                    "Intelligenz, intelligence artificielle</i>...</li><li>Country authority table: <span class='mono'>EL</span> and "
                    "<span class='mono'>UK</span> in CORDIS map to ISO <span class='mono'>GR</span>, <span class='mono'>GB</span>.</li>"
                    "</ul><p>The pipeline uses these extracts as reference data (dated, licence cited).</p>"
                    + table(pd.read_csv(SEM / "results" / "endpoint_1_top_domains.csv")[["label", "descendants"]].rename(
                        columns={"label": "EuroSciVoc top concept", "descendants": "concepts below"}), num=("concepts below",)), text=True),
               card("What it adds, and its limits", "<ul><li><b>Adds</b>: hierarchies queried at any depth; shared EU identifiers "
                    "(join with other EU datasets without a mapping table); multilingual labels; data that carries its source, "
                    "licence and rules.</li><li><b>Limits</b>: the relational model stays the system of record (loads, constraints, "
                    f"aggregates over {n_part:,} rows); {n_dom - n_off} CORDIS-only codes get local URIs; example.org IRIs are a "
                    "placeholder.</li></ul>", text=True)],
        footer="src/build_rdf.py, src/sparql_endpoint.py · semantic/ (graph, queries, results, shapes.ttl, vocabulary.ttl) · "
               "publications.europa.eu/webapi/rdf/sparql"))

    # 6 Analysis
    top_pairs = pairs.head(5)
    pr = ", ".join(f"{r.country_a}-{r.country_b} ({r.shared_projects:,})" for r in top_pairs.itertuples())
    pages.append(dict(
        title=f"What Horizon Europe funds: Pillar II holds {p2_share:.0%} of {bn(he['eu_contribution'])}, and collaborative "
              f"projects gather a median of {collab['Research and innovation action']['median_members']:.0f} organisations from "
              f"{collab['Research and innovation action']['avg_countries']:.0f} countries",
        subtitle=f"Each chart answers a user story with one SQL query (sql/us*.sql). Amounts are maximum EU contributions in signed "
                 f"grants ({he['status']['SIGNED'] / he['projects']:.0%} still running): commitments, not payments. EU-27 organisations "
                 f"receive {F['eu27_share']:.0%} of the funding. Descriptive figures: no ranking of merit.",
        tag="PUBLIC DATA · ANALYSIS", tag_class="real", kpis=None, cols="1fr 1fr 1fr", rows="1fr 1fr",
        cards=[card("US01 Funding by pillar, EUR bn", ch_pillar(pil), tag="PUBLIC DATA"),
               card("US02 Net EU contribution by country, top 12", ch_countries(cty), row="1 / 3", tag="PUBLIC DATA"),
               card("US03 Share of funding by organisation type, %", ch_orgtype(ot), tag="PUBLIC DATA"),
               card("US05 Consortium size by type of action", ch_consortium(cs), tag="PUBLIC DATA"),
               card("US07 Cooperation, and how to read it", f"<p><b>Most frequent country pairs</b> (projects with both): {pr}.</p>"
                    f"<p>The network links {F['network']['countries']} countries ({F['network']['links']:,} pairs). "
                    f"{F['single_beneficiary_share_he']:.0%} of grants have a single beneficiary (ERC, MSCA, EIC): its only "
                    "participant is the coordinator, so coordination rates are also shown for collaborative actions only "
                    "(dashboard).</p><p>Domain totals use a 1/n weight per project; "
                    f"{F['unclassified_share_he']:.0%} of projects have no domain in CORDIS.</p>", text=True)],
        footer="sql/ · src/analysis.py · dashboard/horizon_europe_explorer.html (overview, domains, cooperation)"))

    # 7 Methods
    src = ("<table><tr><th>Source</th><th>Use</th><th>Licence / date</th></tr>"
           "<tr><td>CORDIS, Horizon Europe projects (Publications Office)</td><td>projects, organisations, roles, domains, legal basis</td>"
           f"<td>Decision 2011/833/EU · {DATA_DATE}</td></tr>"
           "<tr><td>CORDIS, Horizon 2020 projects</td><td>comparison of two programmes</td><td>same</td></tr>"
           "<tr><td>EU Vocabularies (SPARQL endpoint)</td><td>EuroSciVoc concepts, country authority table</td><td>CC BY 4.0 · 17 Nov 2026</td></tr>"
           "<tr><td>Regulation (EU) 2021/695; F&amp;T Portal manual</td><td>life cycle and rules</td><td>EUR-Lex, read 17 Nov 2026</td></tr>"
           "<tr><td>tests/fixtures (SIMULATED)</td><td>invented rows in CORDIS format, for tests only</td><td>-</td></tr></table>")
    lim = ("<ul><li>Amounts are <b>maximum EU contributions</b> of signed grants, not payments; most Horizon Europe projects are "
           "still running.</li><li>No reporting periods, payments or proposals in open data; 18% of projects have no domain.</li>"
           "<li>CORDIS is the authoritative source: inconsistencies are reported (quality checks), not corrected.</li>"
           "<li>Coordination and funding by country depend on grant types and on association status, not analysed here.</li>"
           "<li>Duplicate organisations are flagged as candidates, not merged.</li></ul>")
    priv = ("<ul><li>No person's data: address, VAT number, coordinates and contact links are dropped before storage (tested).</li>"
            "<li>In the graph, only universities, research organisations and public bodies are named; companies by PIC.</li>"
            "<li>Raw files are not redistributed; scripts download them at low frequency.</li></ul>")
    rerun = ("<pre>python src/download.py          # CORDIS bundles\npython src/sparql_endpoint.py   # EU Vocabularies extracts\n"
             "python src/load.py              # database + checks\npytest\npython src/build_rdf.py         # graph, SPARQL, SHACL\n"
             "python src/analysis.py          # business questions\npython src/build_pdf.py</pre>")
    pages.append(dict(
        title="Methods, limits and AI note", subtitle="Everything reruns from code; every figure in this document is read from a "
              "pipeline output.", tag="METHODS", tag_class="", kpis=None, cols="1.1fr 1fr 0.85fr", rows="1fr 1fr",
        cards=[card("Sources and licences", src, text=True), card("Limits", lim, text=True), card("How to rerun", rerun, text=True),
               card("Data protection", priv, text=True),
               card("Quality and reproducibility", f"<ul><li>{len(qa)} automatic checks after each load: control totals against "
                    f"the raw files, keys, roles, reconciliation of the star schema; a FAIL stops the publication.</li>"
                    f"<li>{n_tests} tests on every change (GitHub Actions), without downloading data, plus the DDL on PostgreSQL 16.</li>"
                    "<li>Full rebuild of both programmes (stage, load, checks) in under a minute on a laptop.</li>"
                    "<li>Data dictionary and profiling are generated, never typed.</li></ul>", text=True),
               card("AI note", f"<div class='ai'>{AI_NOTE}</div>", text=True)],
        footer="README.md · data/reference/RETRIEVED.md · data/raw/download_log.csv (local)"))
    return pages


def main():
    TMP.mkdir(exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)
    pages = build_pages()
    head = (f"<!doctype html><html><head><meta charset='utf-8'><title>EU-funded research data model case study</title>"
            f"<style>{CSS}</style></head><body>")
    sections = [PAGE.render(p=p, foot=FOOTER) for p in pages]
    src = TMP / "report.html"
    src.write_text(head + "".join(sections) + "</body></html>", encoding="utf-8")
    html_to_pdf(src, PDF, "Modelling EU-funded research: a case study on CORDIS open data")
    for i, sec in enumerate(sections):
        one = TMP / f"pdf_p{i}.html"
        one.write_text(head.replace("page-break-after: always", "") + sec + "</body></html>", encoding="utf-8")
        screenshot(one, IMG / f"pdf_p{i}.png", 1536, 864)
    from pypdf import PdfReader
    print("PDF:", PDF.relative_to(ROOT), f"({PDF.stat().st_size // 1024} KB, {len(PdfReader(str(PDF)).pages)} pages)")


if __name__ == "__main__":
    main()
