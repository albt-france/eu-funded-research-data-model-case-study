"""Self-contained HTML dashboard (Plotly, works offline): dashboard/horizon_europe_explorer.html. PUBLIC DATA.
Three tabs: overview, scientific domains, cooperation. Every figure is computed from the database.
Usage: python src/build_dashboard.py [--db data/cordis.duckdb]
"""
import json
import sys
from pathlib import Path

import duckdb
import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from config import DATA_DATE, DB, FOOTER, PROC, ROOT

OUT = ROOT / "dashboard" / "horizon_europe_explorer.html"
BLUE, BLUE_L, GRAY, GRAY_D, GREEN, INK2 = "#2A78D6", "#86B6EF", "#C9C7BF", "#898781", "#1BAF7A", "#52514E"
SHORT = {"HES": "Higher education", "REC": "Research org.", "PRC": "Companies", "PUB": "Public bodies", "OTH": "Other"}
PROG = {"HORIZON": ("Horizon Europe", BLUE), "H2020": ("Horizon 2020", GRAY_D)}
LAYOUT = dict(font=dict(family="Segoe UI, system-ui, sans-serif", size=12, color=INK2), paper_bgcolor="#FCFCFB",
              plot_bgcolor="#FCFCFB", margin=dict(l=10, r=10, t=40, b=10), legend=dict(orientation="h", y=-0.15))


def fig_html(fig, height=360, first=False):
    fig.update_layout(**LAYOUT, height=height)
    fig.update_xaxes(gridcolor="#E1E0D9")
    fig.update_yaxes(gridcolor="#E1E0D9")
    return pio.to_html(fig, include_plotlyjs="inline" if first else False, full_html=False, config={"displaylogo": False})


def domain_sunburst(con) -> pd.DataFrame:
    """EU contribution allocated to EuroSciVoc domains down to level 3 (weight 1/n per project): additive tree."""
    psd = con.execute("""
        select psd.project_id, psd.domain_code, p.ec_max_contribution
        from project_science_domain psd join project p using (project_id) where p.programme_code = 'HORIZON'""").df()
    psd["node"] = psd.domain_code.str.split("/").str[:4].str.join("/")
    psd = psd.drop_duplicates(["project_id", "node"])
    psd["w"] = 1 / psd.groupby("project_id").node.transform("count")
    psd["value"] = psd.ec_max_contribution.astype(float) * psd.w
    leaf = psd.groupby("node").value.sum()
    labels = dict(con.execute("select domain_code, label from science_domain").fetchall())
    rows = {}
    for node, v in leaf.items():
        parts = node.strip("/").split("/")
        for i in range(1, len(parts) + 1):
            code = "/" + "/".join(parts[:i])
            rows[code] = rows.get(code, 0) + v
    df = pd.DataFrame({"id": list(rows), "value": list(rows.values())})
    df["parent"] = df.id.map(lambda c: c.rsplit("/", 1)[0] if c.count("/") > 1 else "")
    df["label"] = df.id.map(labels)
    return df


def main(argv=None):
    argv = argv or sys.argv[1:]
    db = Path(argv[argv.index("--db") + 1]) if "--db" in argv else DB
    con = duckdb.connect(str(db), read_only=True)
    F = json.loads((PROC / "findings.json").read_text(encoding="utf-8"))
    he = F["HORIZON"]
    charts = {}

    # ---------- overview
    pil = pd.read_csv(PROC / "us01_funding_by_pillar.csv")
    d = pil[pil.programme_code == "HORIZON"].sort_values("eu_contribution_bn")
    fig = go.Figure(go.Bar(y=d.pillar_title.str.replace(" - ", ": ").str.replace("Strengthening the European Research Area", "ERA"),
                           x=d.eu_contribution_bn, orientation="h", marker_color=BLUE,
                           text=d.eu_contribution_bn.map(lambda v: f"EUR {v:.1f} bn"), textposition="outside"))
    fig.update_layout(title="Horizon Europe: maximum EU contribution by pillar", yaxis=dict(automargin=True),
                      xaxis=dict(range=[0, d.eu_contribution_bn.max() * 1.4]))
    charts["pillar"] = fig_html(fig, 360, first=True)
    st = pd.Series(he["status"]).rename({"SIGNED": "Signed (running)", "CLOSED": "Closed", "TERMINATED": "Terminated"})
    fig = go.Figure(go.Pie(labels=st.index, values=st.values, hole=0.55, marker=dict(colors=[BLUE, GREEN, GRAY]), sort=False))
    fig.update_layout(title="Horizon Europe projects by status: most grants are still running")
    charts["status"] = fig_html(fig, 360)
    yr = pd.read_csv(PROC / "us08_projects_by_start_year.csv").dropna(subset=["start_year"])
    fig = go.Figure()
    for prog, (name, col) in PROG.items():
        d = yr[yr.programme_code == prog]
        fig.add_bar(x=d.start_year.astype(int), y=d.projects, name=name, marker_color=col)
    fig.update_layout(title="Projects by start year (programmes overlap: H2020 grants signed until 2022)", barmode="stack")
    charts["year"] = fig_html(fig)

    ot = pd.read_csv(PROC / "us03_funding_by_org_type.csv").dropna(subset=["type_code"])
    fig = go.Figure()
    for prog, (name, col) in PROG.items():
        d = ot[ot.programme_code == prog]
        fig.add_bar(x=d.type_code.map(SHORT), y=d.share_pct, name=name, marker_color=col,
                    text=d.share_pct.map(lambda v: f"{v:.0f}%"), textposition="outside")
    fig.update_layout(title="Share of EU contribution by organisation type (%)", barmode="group")
    charts["orgtype"] = fig_html(fig)

    cs = pd.read_csv(PROC / "us05_consortium_size.csv").merge(pd.read_csv(PROC / "us06_duration_and_size.csv"), on=["action_family", "projects"])
    tbl = go.Figure(go.Table(
        header=dict(values=["Type of action", "Projects", "Median members", "Avg countries", "Single beneficiary", "Median grant (EUR m)",
                            "Median months"], fill_color="#F1F0EB", align="left"),
        cells=dict(values=[cs.action_family, cs.projects.map("{:,}".format), cs.median_members, cs.avg_countries,
                           cs.single_beneficiary_pct.map(lambda v: f"{v:.0f}%"), cs.median_grant_m, cs.median_months],
                   fill_color="#FCFCFB", align="left")))
    tbl.update_layout(title="Horizon Europe by type of action")
    charts["actions"] = fig_html(tbl, 330)

    # ---------- domains
    sb = domain_sunburst(con)
    fig = go.Figure(go.Sunburst(ids=sb.id, labels=sb.label, parents=sb.parent, values=sb.value / 1e9, branchvalues="total",
                                hovertemplate="%{label}<br>EUR %{value:.2f} bn<extra></extra>", maxdepth=2))
    fig.update_layout(sunburstcolorway=[BLUE, GREEN, "#EDA100", "#D03B3B", "#7F55B1", "#3FA7B5"], extendsunburstcolors=True)
    fig.update_layout(title="Horizon Europe funding by EuroSciVoc domain, 3 levels (EUR bn, weight 1/n per project; click to zoom)")
    charts["sunburst"] = fig_html(fig, 560)
    dm = pd.read_csv(PROC / "us04_funding_by_domain.csv")
    fig = go.Figure()
    for prog, (name, col) in PROG.items():
        d = dm[dm.programme_code == prog].sort_values("eu_contribution_bn")
        fig.add_bar(y=d.domain, x=d.eu_contribution_bn, orientation="h", name=name, marker_color=col)
    fig.update_layout(title="By top-level domain, EUR bn ('not classified' = no EuroSciVoc code in CORDIS)", barmode="group")
    charts["domains"] = fig_html(fig, 420)
    ai = pd.read_csv(ROOT / "semantic" / "results" / "graph_01_domain_tree.csv").head(12).iloc[::-1]
    fig = go.Figure(go.Bar(y=ai.label, x=ai.projects, orientation="h", marker_color=BLUE_L))
    fig.update_layout(title="'Artificial intelligence' and its sub-domains: projects (SPARQL, skos:broader*)")
    charts["ai"] = fig_html(fig, 420)

    # ---------- cooperation
    cty = pd.read_csv(PROC / "us02_funding_by_country.csv").merge(
        con.execute("select country_code, iso3_code from country").df(), on="country_code", how="left")
    fig = go.Figure(go.Choropleth(locations=cty.iso3_code, z=cty.eu_contribution_bn, text=cty.country, colorscale="Blues",
                                  hovertemplate="%{text}<br>EUR %{z:.2f} bn<extra></extra>", colorbar_title="EUR bn"))
    fig.update_geos(scope="europe", projection_type="natural earth", showcountries=True, countrycolor="#E1E0D9",
                    lataxis_range=[33, 72], lonaxis_range=[-25, 45])
    fig.update_layout(title="Net EU contribution by participant country, Horizon Europe")
    charts["map"] = fig_html(fig, 520)

    pairs = pd.read_csv(PROC / "us07_country_network.csv")
    top = cty.dropna(subset=["country_code"]).head(25).country_code.tolist()
    sub = pairs[pairs.country_a.isin(top) & pairs.country_b.isin(top)].head(80)
    g = nx.Graph()
    for r in sub.itertuples():
        g.add_edge(r.country_a, r.country_b, weight=r.shared_projects)
    pos = nx.spring_layout(g, weight="weight", seed=7, k=0.9)
    fig = go.Figure()
    wmax = sub.shared_projects.max()
    for r in sub.itertuples():
        (x0, y0), (x1, y1) = pos[r.country_a], pos[r.country_b]
        fig.add_scatter(x=[x0, x1], y=[y0, y1], mode="lines", line=dict(width=0.5 + 5 * r.shared_projects / wmax, color=BLUE_L),
                        hoverinfo="skip", showlegend=False, opacity=0.7)
    strength = dict(g.degree(weight="weight"))
    nodes = list(g.nodes)
    fig.add_scatter(x=[pos[n][0] for n in nodes], y=[pos[n][1] for n in nodes], mode="markers+text", text=nodes,
                    textposition="middle center", marker=dict(size=[12 + 30 * strength[n] / max(strength.values()) for n in nodes],
                                                               color=BLUE, line=dict(color="white", width=1)),
                    textfont=dict(color="white", size=10), showlegend=False,
                    hovertext=[f"{n}: {strength[n]:,} shared-project links" for n in nodes], hoverinfo="text")
    fig.update_layout(title="Cooperation network: 80 strongest country pairs among the 25 largest participants",
                      xaxis=dict(visible=False), yaxis=dict(visible=False))
    charts["network"] = fig_html(fig, 520)

    co = pd.read_csv(PROC / "us09_coordination_share.csv").head(20).iloc[::-1]
    fig = go.Figure()
    fig.add_bar(y=co.country, x=co.coordination_rate_pct, orientation="h", name="All actions", marker_color=GRAY)
    fig.add_bar(y=co.country, x=co.collaborative_coordination_rate_pct, orientation="h", name="Collaborative actions (RIA, IA, CSA)",
                marker_color=BLUE)
    fig.update_layout(title="Coordinations per 100 participations (20 largest participants)", barmode="group")
    charts["coord"] = fig_html(fig, 560)
    con.close()

    kpis = [("Horizon Europe projects", f"{he['projects']:,}", f"{he['status']['SIGNED']:,} still running"),
            ("Maximum EU contribution", f"EUR {he['eu_contribution'] / 1e9:.1f} bn", "committed, not paid"),
            ("Participations", f"{he['participations']:,}", f"{he['organisations']:,} organisations"),
            ("Countries", f"{he['countries']}", f"EU-27: {F['eu27_share']:.0%} of the funding"),
            ("Single-beneficiary grants", f"{F['single_beneficiary_share_he']:.0%}", "ERC, MSCA, EIC")]
    kpi_html = "".join(f"<div class='kpi'><div class='kl'>{a}</div><div class='kv'>{b}</div><div class='kn'>{c}</div></div>"
                       for a, b, c in kpis)
    tabs = {"overview": ("Overview", ["pillar", "status", "year", "orgtype", "actions"]),
            "domains": ("Scientific domains", ["sunburst", "domains", "ai"]),
            "coop": ("Cooperation", ["map", "network", "coord"])}
    body = ""
    for i, (tid, (title, keys)) in enumerate(tabs.items()):
        cards = "".join(f"<div class='card{' wide' if k in ('sunburst', 'map', 'network', 'actions', 'coord') else ''}'>{charts[k]}</div>" for k in keys)
        body += f"<section id='{tid}' class='tab' style='display:{'grid' if i == 0 else 'none'}'>{cards}</section>"
    buttons = "".join(f"<button onclick=\"show('{t}')\" id='b-{t}' class='{'on' if i == 0 else ''}'>{v[0]}</button>"
                      for i, (t, v) in enumerate(tabs.items()))
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Horizon Europe explorer</title><style>
body{{font-family:'Segoe UI',system-ui,sans-serif;background:#F4F4F2;color:#0B0B0B;margin:0;padding:20px 28px}}
h1{{font-size:22px;margin:0 0 4px}} .sub{{color:#52514E;font-size:13px;margin-bottom:12px}}
.tag{{display:inline-block;font-size:11px;font-weight:700;color:#0E7A55;border:1px solid #8FD3B8;border-radius:4px;padding:2px 7px;margin-left:8px}}
.kpis{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:10px 0 14px}}
.kpi,.card{{background:#FCFCFB;border:1px solid #E1E0D9;border-radius:8px;padding:10px 14px}}
.kl{{font-size:11px;font-weight:700;color:#52514E;text-transform:uppercase;letter-spacing:.4px}} .kv{{font-size:24px;font-weight:700;color:#1C5CAB}}
.kn{{font-size:12px;color:#52514E}} nav button{{font:inherit;border:1px solid #C9C7BF;background:#FCFCFB;border-radius:6px;padding:6px 14px;margin-right:6px;cursor:pointer}}
nav button.on{{background:#2A78D6;color:white;border-color:#2A78D6}} .tab{{grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}}
.card.wide{{grid-column:1 / 3}} footer{{font-size:11px;color:#898781;margin-top:16px}}
@media (max-width:900px){{.kpis{{grid-template-columns:1fr 1fr}} .tab{{grid-template-columns:1fr}} .card.wide{{grid-column:auto}}}}
</style></head><body>
<h1>Horizon Europe explorer<span class="tag">PUBLIC DATA</span></h1>
<div class="sub">CORDIS open data (Publications Office of the EU), Horizon Europe and Horizon 2020, downloaded {DATA_DATE}. Amounts are the maximum
EU contribution in signed grants (commitments, not payments). Funding by organisation and country uses the net contribution of funded roles.</div>
<div class="kpis">{kpi_html}</div><nav>{buttons}</nav>{body}
<footer>{FOOTER} · Source: CORDIS, reuse under Commission Decision 2011/833/EU · EuroSciVoc and country table: EU Vocabularies.
Descriptive figures: they do not rank organisations or countries.</footer>
<script>function show(t){{document.querySelectorAll('.tab').forEach(s=>s.style.display=s.id===t?'grid':'none');
document.querySelectorAll('nav button').forEach(b=>b.className=b.id==='b-'+t?'on':'');window.dispatchEvent(new Event("resize"));}}
if(location.hash) show(location.hash.slice(1));</script>
</body></html>"""
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print("dashboard:", OUT.relative_to(ROOT), f"{OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
