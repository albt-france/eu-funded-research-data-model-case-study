# Requirements: user stories, acceptance criteria and non-functional requirements

Users of a reporting and data system for EU-funded research programmes. Each story names the query that answers it
(`sql/` on the relational model, `semantic/queries/` on the graph) and the test or check that proves the criteria.
Stories 13 and 14 are about data the open data does not contain: they shape the model but stay open.

## Actors

| Actor | Needs |
|---|---|
| **Programme manager** | follows the portfolio of a programme part: money, projects, timing |
| **Policy analyst** | compares countries, organisation types and scientific domains; looks at cooperation |
| **Project officer** | follows individual grants: consortium, roles, reporting, payments |
| **Data steward** | loads new CORDIS releases, guarantees quality, lineage and data protection |
| **External data user** | reuses the data with other EU datasets (shared identifiers, open formats) |

## User stories

| # | As a... | I want... | So that... | Answered by |
|---|---|---|---|---|
| US01 | programme manager | the EU contribution and number of projects by programme and pillar | I can see where the budget is committed | `sql/us01_funding_by_pillar.sql` |
| US02 | policy analyst | the EU contribution, participations and coordinations by country | I can describe the geographic spread | `sql/us02_funding_by_country.sql` |
| US03 | policy analyst | the share of funding by organisation type (universities, research organisations, companies, public bodies) | I can describe who receives the funding | `sql/us03_funding_by_org_type.sql` |
| US04 | policy analyst | the EU contribution by scientific domain without double counting | domain totals add up to the programme total | `sql/us04_funding_by_domain.sql` (weighted bridge) |
| US05 | project officer | the size of consortia and number of countries by type of action | I know what a typical consortium looks like | `sql/us05_consortium_size.sql` |
| US06 | programme manager | the typical grant size and duration by type of action | I can plan monitoring workload | `sql/us06_duration_and_size.sql` |
| US07 | policy analyst | the cooperation network between countries | I can see which countries work together | `sql/us07_country_network.sql`, `graph_03_country_pairs.rq` |
| US08 | programme manager | projects and funding by start year, for Horizon Europe and Horizon 2020 | I can compare the two programmes over time | `sql/us08_projects_by_start_year.sql` |
| US09 | policy analyst | the share of participations that are coordinations, by country | I can describe who leads projects, taking single-beneficiary grants into account | `sql/us09_coordination_share.sql` |
| US10 | policy analyst | all projects in a domain **and all its sub-domains** | a search on "artificial intelligence" also finds "machine learning" | `sql/us10_domain_drilldown.sql` (recursive), `graph_01_domain_tree.rq` (SKOS path) |
| US11 | data steward | to know for every project which file and load it comes from | any figure can be traced back to its source | `sql/us11_lineage.sql`, table `load_batch` |
| US12 | policy analyst | the share of participations and funding going to SMEs | I can follow SME participation | `sql/us12_sme_participation.sql` |
| US13 | project officer | the reporting periods and due dates of each grant | I can follow late reports | table `reporting_period` (modelled, **no open data**) |
| US14 | external data user | countries and domains identified by EU Vocabularies URIs | I can join this data with other EU datasets | `semantic/graph/*.ttl`, `endpoint_*.rq` |

## Acceptance criteria (Given / When / Then)

**US01 - Funding by pillar**
- *Given* a load of the Horizon Europe bundle, *when* I group projects by pillar, *then* every project has exactly one pillar
  and the sum over pillars equals the total maximum EU contribution of the bundle (checks Q05, Q16).
- *Given* a project funded under a sub-part (e.g. `HORIZON.2.5.2`), *when* I ask for its pillar, *then* I get the top of its
  legal-basis hierarchy (Pillar II), whatever the depth.

**US02 - Funding by country**
- *Given* CORDIS codes `EL` and `UK`, *when* the data is loaded, *then* they are reported as Greece (`GR`) and United Kingdom
  (`GB`) and join the EU country authority table (`test_amounts_dates_and_codes_are_cleaned`).
- *Given* a participation without a country, *when* I group by country, *then* it is shown as unknown, not dropped (Q09).

**US03 - Organisation types**
- *Given* an affiliated entity with 0 gross and a positive net contribution, *when* I sum funding, *then* its net amount is
  counted once (`test_unfunded_role_gets_zero_and_affiliated_entity_keeps_net_amount`).
- *Given* an associated partner, *when* I sum funding, *then* it counts for 0, even if the source shows an amount (Q06).

**US04 - Domains without double counting**
- *Given* a project classified in two top-level domains, *when* I split funding by domain, *then* each domain gets half and
  the domain total equals the programme total (Q17).
- *Given* an unclassified project, *then* it appears as "(not classified)".

**US05 / US06 - Consortia, grant size and duration**
- *Given* the participations of a project, *when* I count its members, *then* an organisation that left and re-joined is
  counted once (distinct PIC).
- *Given* a grant with a total cost of 0 in CORDIS, *then* the cost is "not reported" (NULL), never a real zero.

**US07 / US09 - Cooperation and coordination**
- *Given* two organisations of the same country in one project, *when* I build country pairs, *then* the pair is not counted
  with itself, and each project counts once per pair.
- *Given* single-beneficiary grants, *then* the coordination rate is also shown for collaborative actions only.

**US10 - Domain drill-down**
- *Given* the domain "artificial intelligence", *when* I query it, *then* projects classified only under "machine learning"
  or "deep learning" are included; SQL and SPARQL return the same number of projects (1,263 for Horizon Europe).

**US11 - Lineage**
- *Given* any project row, *then* it has a `batch_id` pointing to the source URL, download time, rows read and lines repaired.
- *Given* a new load, *then* raw row counts and the raw EU contribution total equal the loaded ones, or the load fails (Q03-Q05).

**US12 - SMEs**
- *Given* an organisation that is an SME in one project and not in a later one, *then* each participation keeps its own
  status (`test_sme_status_is_kept_per_participation`).

**US13 - Reporting periods (open)**
- *Given* the operational system, *when* reporting periods are available, *then* `reporting_period` stores one row per period
  with its due date; *today* check Q15 states that the table is empty because CORDIS does not publish it.

**US14 - Interoperability**
- *Given* the graph, *then* every country is an EU authority URI and every domain present in EuroSciVoc uses its official URI;
  SHACL validation passes and fails on a project without a coordinator (`test_semantic.py`).

## Non-functional requirements

| Id | Requirement | How it is met |
|---|---|---|
| NFR1 Quality | A load is rejected if row counts or the EU contribution total differ from the raw files, or if a project has no or several coordinators. | 18 checks after each load (`src/quality.py`), FAIL stops, WARN is reported ([QA_REPORT.md](QA_REPORT.md)) |
| NFR2 Traceability | Every figure can be traced to a file, a download date and a rule. | `load_batch`, `download_log.csv`, cleaning log, figures read from `data/processed/` |
| NFR3 Refresh | A new CORDIS release is loaded with two commands; the load is idempotent (full rebuild). | `python src/download.py`, `python src/load.py`; 38 seconds measured on a laptop for both programmes (stage, load, checks) |
| NFR4 Data protection | No personal data is stored or published. | Personal and address columns dropped at staging (tested); company names not published in the graph |
| NFR5 Integrity | Business rules are enforced by the database, not only by code. | Keys, foreign keys, checks (DuckDB and PostgreSQL); partial unique index for one coordinator (PostgreSQL) |
| NFR6 Portability | The model runs on DuckDB and PostgreSQL. | `schema.sql` applied to PostgreSQL 16 in CI |
| NFR7 Interoperability | Reference data uses EU Vocabularies. | Country authority table and EuroSciVoc from the Publications Office endpoint |
| NFR8 Reproducibility | Tests run on every change, without downloading data. | SIMULATED fixtures in CORDIS format, GitHub Actions |
