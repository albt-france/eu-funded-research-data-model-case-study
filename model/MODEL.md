# The data model: conceptual, logical, physical

All diagrams: [DIAGRAMS.md](DIAGRAMS.md) (rendered by GitHub). Physical model: [`ddl/schema.sql`](ddl/schema.sql)
(DuckDB, also valid PostgreSQL), [`ddl/schema_postgres.sql`](ddl/schema_postgres.sql) (PostgreSQL additions),
[`ddl/mart.sql`](ddl/mart.sql) (star schema). Every table and column: [DATA_DICTIONARY.md](DATA_DICTIONARY.md).

## 1. Conceptual model: the business, without technique

Built from the life cycle in [BUSINESS_CONTEXT.md](../docs/analysis/BUSINESS_CONTEXT.md), not from the files.
A **framework programme** is structured in **programme parts** (a tree: pillar > cluster > destination), and opens **calls**
made of **topics**. A **project** answers one topic, is funded under one main programme part with one type of action
(**funding scheme**), and is classified in **scientific domains** (EuroSciVoc, a tree). **Organisations** take part in projects;
the **participation** carries the role (coordinator, beneficiary, affiliated entity, associated partner) and the money.
A project produces **deliverables** and is followed through **reporting periods**.

## 2. Logical model: entities, keys, cardinalities (3NF)

| Choice | Why |
|---|---|
| `participation` is an **association entity** between project and organisation, with its own attributes (role, order, contribution, SME status, ended) | the many-to-many relation carries data: it is the grain of the analysis (330,445 rows) |
| Natural key of a participation = (project, organisation, role, order); surrogate key `participation_id` | profiling showed (project, organisation, role) is not unique: an organisation can leave and re-join |
| `project_science_domain` and `project_programme_part` association tables | a project has several domains and can draw on several programme parts (one flagged as main) |
| Hierarchies as **self-references** (`science_domain.parent_code`, `programme_part.parent_part_code`) | depth varies (up to 7 levels for domains); one recursive query answers "all sub-domains" |
| **Reference tables** for country, organisation type, role, funding scheme | one place for labels and groupings (e.g. the six CORDIS role codes in four role groups), no repeated text |
| `load_batch` on every project | lineage: source file, download date, lines repaired |
| `reporting_period` modelled although empty | the business needs it (US13); the open data does not publish it. Modelling the business, not the file, shows the gap |

**Normalisation.** 1NF: no multi-valued column (CORDIS `legalBasis` lists several codes in one H2020 field and
`country` once holds `DE;HU`: split or resolved at load). 2NF: no attribute depends on part of a composite key
(the association tables carry nothing but their keys, except `is_main`, which depends on both). 3NF: no transitive
dependency: the organisation name depends on the PIC, so it is in `organisation`, not repeated in 330,445 participation
rows; the role group depends on the role, so it is in `participant_role`.

**Historisation: the SME flag.** Profiling tested the functional dependency PIC → SME: it does not hold for 340
organisations, whose SME status changes from one project to the next. The status is a fact about the participation at that
time, so it is stored in `participation`, not in `organisation`. Organisation attributes that do not change (name, country,
type: 0 violations) stay in `organisation`, taken from the most recent CORDIS record. A full slowly changing dimension
(validity dates) was not needed for this data.

## 3. Physical model

- **Types:** `DECIMAL(15,2)` for euros (no floating-point rounding), `DATE`, `BIGINT` for project ids and PICs,
  `CHAR(2)` ISO country codes.
- **Constraints carry the business rules:** primary and foreign keys; checks on amounts (≥ 0), dates (end ≥ start), status
  values and role groups; uniqueness of the participation natural key. `tests/test_schema.py` inserts eight invalid rows and
  checks that the database rejects each one.
- **Indexes** on the foreign keys used in joins and filters (project by programme, topic, start date; participation by
  project and organisation; domain links).
- **Descriptions** are `COMMENT ON` statements in the DDL; the data dictionary is generated from the catalogue.
- **DuckDB / PostgreSQL:** the same `schema.sql` runs on both (applied to PostgreSQL 16 in CI). PostgreSQL adds what DuckDB
  lacks: a **partial unique index** that enforces "at most one coordinator per project", a GIN full-text index on objectives,
  and an identity column. In DuckDB the coordinator rule is a quality check (Q01). DuckDB checks foreign keys at insert time,
  including self-references, so hierarchies are loaded parent level first.

## 4. The analytical variant: a star schema, and why both are kept

[`ddl/mart.sql`](ddl/mart.sql) builds views: `fact_participation` (one organisation in one project in one role; measure =
net EU contribution of funded roles), `dim_project` (with pillar, type of action, duration, consortium size),
`dim_organisation`, and `bridge_project_domain`, which gives each project a weight of 1/n across its n top-level domains so
that funding by domain adds up to the total.

| | Normalised model (3NF) | Star schema |
|---|---|---|
| Purpose | system of record: load, constraints, updates | reporting and dashboards |
| Strength | no redundancy, rules enforced, one place per fact | few joins, readable dimensions, additive measure |
| Here | tables in `schema.sql` | views in `mart.sql`, derived only |

The star is derived from the normalised model and never edited, so the two cannot disagree; check Q16 compares their totals
after each load. Pre-computed dimensions (pillar, consortium size) would otherwise need recursive queries and sub-queries in
every report.

## 5. ER diagram or UML class diagram?

The **ER diagram** describes stored data: tables, keys, cardinalities, foreign keys. The **UML class diagram** describes the
domain as objects: attributes **and behaviour** (`Project.durationMonths()`, `ScienceDomain.descendants()`,
`Participation.isFunded()`), enumerations (`ProjectStatus`, `Role`), composition (a project owns its participations) and an
association class (`Participation`). The same reality, two audiences: the ER diagram for the database, the class diagram for
the developers of an application on top of it.
