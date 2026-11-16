# Diagrams

Diagrams as code: the `.mmd` files are the source; GitHub renders the blocks below; `python src/build_diagrams.py` renders SVG and PNG for the report.

## Use case diagram (UML)

Source: [`diagrams/01_use_cases.mmd`](diagrams/01_use_cases.mmd) · image: [`01_use_cases.svg`](diagrams/01_use_cases.svg)

```mermaid
flowchart TB
  PM(["Programme manager"])
  PA(["Policy analyst"])
  PO(["Project officer"])
  DS(["Data steward"])
  EU(["External data user"])
  subgraph SYS["EU research programme data system"]
    UC1(("Follow funding<br/>by pillar and year"))
    UC2(("Compare countries,<br/>organisation types, SMEs"))
    UC3(("Explore a domain<br/>and its sub-domains"))
    UC4(("Analyse cooperation<br/>between countries"))
    UC5(("Inspect a grant:<br/>consortium and roles"))
    UC6(("Follow reporting<br/>periods - no open data"))
    UC7(("Load a CORDIS release"))
    UC8(("Run quality checks"))
    UC9(("Query the graph<br/>with SPARQL"))
  end
  PM --- UC1
  PM --- UC5
  PA --- UC2
  PA --- UC3
  PA --- UC4
  PO --- UC5
  PO --- UC6
  DS --- UC7
  UC7 -. "include" .-> UC8
  EU --- UC9
  UC3 -. "extend" .-> UC9
```

## Activity diagram: life cycle of a grant (UML)

Source: [`diagrams/02_activity_lifecycle.mmd`](diagrams/02_activity_lifecycle.mmd) · image: [`02_activity_lifecycle.svg`](diagrams/02_activity_lifecycle.svg)

```mermaid
flowchart LR
  start((start))
  subgraph CO["Consortium: coordinator and beneficiaries"]
    A2["Register PICs,<br/>submit proposal"]
    A8["Implement the action:<br/>deliverables, milestones"]
    A10["Periodic report: technical<br/>and financial, within 60 days"]
    A13{"Last<br/>period?"}
  end
  subgraph GA["Granting authority: Commission or agency"]
    A1["Publish work programme<br/>and calls with topics"]
    A3{"Admissible<br/>and eligible?"}
    A5{"Funded?"}
    A6["Grant preparation"]
    A7["Sign grant agreement<br/>within 8 months of deadline"]
    A9["Pay pre-financing"]
    A11{"Report<br/>accepted?"}
    A12["Interim payment<br/>within 90 days"]
    A14["Final payment:<br/>balance"]
  end
  subgraph EX["Independent experts"]
    A4["Evaluate: excellence, impact,<br/>quality of implementation"]
  end
  stop((end))
  rej((not funded))
  start --> A1 --> A2 --> A3
  A3 -- no --> rej
  A3 -- yes --> A4 --> A5
  A5 -- "no, informed within 5 months" --> rej
  A5 -- yes --> A6 --> A7 --> A9 --> A8
  A8 --> A10 --> A11
  A11 -- "no: corrections" --> A10
  A11 -- yes --> A13
  A13 -- no --> A12 --> A8
  A13 -- yes --> A14 --> stop
```

## Conceptual model

Source: [`diagrams/03_conceptual.mmd`](diagrams/03_conceptual.mmd) · image: [`03_conceptual.svg`](diagrams/03_conceptual.svg)

```mermaid
erDiagram
  FRAMEWORK_PROGRAMME ||--|{ PROGRAMME_PART : "is structured in"
  PROGRAMME_PART |o--o{ PROGRAMME_PART : "contains"
  FRAMEWORK_PROGRAMME ||--|{ CALL : "opens"
  CALL ||--|{ TOPIC : "has"
  TOPIC ||--o{ PROJECT : "is answered by"
  PROGRAMME_PART ||--o{ PROJECT : "funds"
  FUNDING_SCHEME ||--o{ PROJECT : "is the type of action of"
  PROJECT ||--|{ PARTICIPATION : "has"
  ORGANISATION ||--o{ PARTICIPATION : "takes part through"
  ROLE ||--o{ PARTICIPATION : "qualifies"
  COUNTRY ||--o{ ORGANISATION : "hosts"
  PROJECT }o--o{ SCIENCE_DOMAIN : "is classified in"
  SCIENCE_DOMAIN |o--o{ SCIENCE_DOMAIN : "is broader than"
  PROJECT ||--o{ DELIVERABLE : "produces"
  PROJECT ||--o{ REPORTING_PERIOD : "is reported by"
```

## Logical model: entity-relationship diagram

Source: [`diagrams/04_logical_er.mmd`](diagrams/04_logical_er.mmd) · image: [`04_logical_er.svg`](diagrams/04_logical_er.svg)

```mermaid
erDiagram
  framework_programme ||--|{ programme_part : "structures"
  programme_part |o--o{ programme_part : "parent of"
  framework_programme ||--|{ call : "opens"
  framework_programme ||--|{ topic : "defines"
  framework_programme ||--|{ funding_scheme : "offers"
  programme_part ||--o{ project : "main part of"
  call ||--o{ project : "selects"
  topic ||--o{ project : "answered by"
  funding_scheme ||--o{ project : "type of"
  load_batch ||--|{ project : "loads"
  project ||--|{ participation : "has"
  organisation ||--|{ participation : "takes part"
  participant_role ||--o{ participation : "role of"
  country |o--o{ organisation : "location of"
  organisation_type |o--o{ organisation : "type of"
  project ||--o{ project_science_domain : "classified"
  science_domain ||--o{ project_science_domain : "classifies"
  science_domain |o--o{ science_domain : "parent of"
  project ||--o{ project_programme_part : "drawn on"
  programme_part ||--o{ project_programme_part : "funds"
  project ||--o{ project_document : "publishes"
  project ||--o{ reporting_period : "reported in"

  project {
    bigint project_id PK
    varchar acronym
    varchar status "SIGNED CLOSED TERMINATED"
    varchar programme_code FK
    varchar main_part_code FK
    varchar call_code FK
    varchar topic_code FK
    varchar scheme_code FK
    date start_date
    date end_date "end >= start"
    decimal total_cost "NULL = not reported"
    decimal ec_max_contribution ">= 0"
    int batch_id FK
  }
  participation {
    bigint participation_id PK
    bigint project_id FK
    bigint organisation_id FK
    varchar role_code FK
    smallint order_no "unique with project, org, role"
    decimal net_ec_contribution
    boolean is_sme "status at that time"
    boolean has_ended
  }
  organisation {
    bigint organisation_id PK "PIC"
    varchar legal_name
    varchar name_key
    varchar type_code FK
    char country_code FK
    varchar nuts_code
  }
  science_domain {
    varchar domain_code PK "e.g. /23/53/373"
    varchar notation "EuroSciVoc notation"
    varchar label
    varchar parent_code FK
    smallint depth
    varchar euroscivoc_uri
  }
  programme_part {
    varchar part_code PK
    varchar programme_code FK
    varchar parent_part_code FK
    varchar title
    smallint depth
  }
  participant_role {
    varchar role_code PK
    varchar role_group
    boolean receives_eu_funding
  }
  country {
    char country_code PK "ISO alpha-2"
    char iso3_code
    varchar name
    boolean is_eu27
  }
  project_science_domain {
    bigint project_id PK, FK
    varchar domain_code PK, FK
  }
  reporting_period {
    bigint project_id PK, FK
    smallint period_no PK
    date start_date
    date end_date
    date report_due_date
  }
  load_batch {
    int batch_id PK
    varchar source_url
    timestamp downloaded_utc
    int rows_read
    int lines_repaired
  }
```

## Class diagram (UML)

Source: [`diagrams/05_class_uml.mmd`](diagrams/05_class_uml.mmd) · image: [`05_class_uml.svg`](diagrams/05_class_uml.svg)

```mermaid
classDiagram
  direction LR
  class FrameworkProgramme {
    +code: String
    +name: String
    +period: YearRange
  }
  class ProgrammePart {
    +code: String
    +title: String
    +pillar() ProgrammePart
  }
  class Call {
    +code: String
  }
  class Topic {
    +code: String
    +title: String
  }
  class Project {
    +id: Long
    +acronym: String
    +status: ProjectStatus
    +startDate: Date
    +endDate: Date
    +ecMaxContribution: Money
    +durationMonths() int
    +coordinator() Organisation
    +consortiumSize() int
  }
  class Participation {
    <<association class>>
    +role: Role
    +order: int
    +netEcContribution: Money
    +isSme: Boolean
    +hasEnded: Boolean
    +isFunded() Boolean
  }
  class Organisation {
    +pic: Long
    +legalName: String
    +type: OrganisationType
  }
  class Country {
    +isoCode: String
    +name: String
    +isEu27: Boolean
  }
  class ScienceDomain {
    +notation: String
    +label: String
    +descendants() List~ScienceDomain~
  }
  class ProjectStatus {
    <<enumeration>>
    SIGNED
    CLOSED
    TERMINATED
  }
  class Role {
    <<enumeration>>
    COORDINATOR
    BENEFICIARY
    AFFILIATED_ENTITY
    ASSOCIATED_PARTNER
  }
  class Deliverable {
    +url: String
    +type: String
  }
  FrameworkProgramme "1" *-- "1..*" ProgrammePart : structured in
  ProgrammePart "0..1" o-- "0..*" ProgrammePart : parent
  FrameworkProgramme "1" --> "1..*" Call : opens
  Call "1" --> "1..*" Topic
  Project "0..*" --> "1" Topic : answers
  Project "0..*" --> "1" ProgrammePart : funded under
  Project "1" *-- "1..*" Participation
  Participation "0..*" --> "1" Organisation
  Organisation "0..*" --> "0..1" Country
  Project "0..*" --> "0..*" ScienceDomain : classified in
  ScienceDomain "0..1" o-- "0..*" ScienceDomain : broader
  Project "1" *-- "0..*" Deliverable
  Project ..> ProjectStatus
  Participation ..> Role
```

## Sequence diagram: loading a CORDIS release (UML)

Source: [`diagrams/06_sequence_load.mmd`](diagrams/06_sequence_load.mmd) · image: [`06_sequence_load.svg`](diagrams/06_sequence_load.svg)

```mermaid
sequenceDiagram
  autonumber
  actor DS as Data steward
  participant DL as download.py
  participant CO as CORDIS (Publications Office)
  participant ST as stage.py and cordis_io
  participant LD as load.py
  participant DB as DuckDB (schema.sql)
  participant QA as quality.py
  DS->>DL: python src/download.py
  DL->>CO: GET cordis-HORIZONprojects-csv.zip
  CO-->>DL: zip, about 38 MB
  DL->>DL: log URL, date and size
  DS->>LD: python src/load.py
  LD->>ST: stage(raw files)
  loop each CSV file
    ST->>ST: split lines, repair broken quotes
    ST->>ST: drop personal and address columns
  end
  ST-->>LD: parquet files and parse statistics
  LD->>LD: clean amounts, dates, ISO countries, build tables
  LD->>DB: CREATE tables with keys, checks, comments
  loop tables in foreign-key order
    LD->>DB: INSERT, hierarchies parent level first
    alt constraint violated
      DB-->>LD: error, the load stops
    end
  end
  LD->>DB: CREATE mart views (star schema)
  LD->>QA: run_checks()
  QA->>DB: 18 counting queries and raw control totals
  QA-->>DS: QA_REPORT.md with PASS, WARN, FAIL
```

## Analytical variant: star schema

Source: [`diagrams/07_star_schema.mmd`](diagrams/07_star_schema.mmd) · image: [`07_star_schema.svg`](diagrams/07_star_schema.svg)

```mermaid
erDiagram
  dim_project ||--o{ fact_participation : "project"
  dim_organisation ||--o{ fact_participation : "organisation"
  country ||--o{ fact_participation : "country"
  participant_role ||--o{ fact_participation : "role"
  dim_project ||--o{ bridge_project_domain : "weight 1/n"
  science_domain ||--o{ bridge_project_domain : "top domain"
  fact_participation {
    bigint participation_id
    bigint project_id FK
    bigint organisation_id FK
    char country_code FK
    varchar role_group
    int start_year
    decimal net_ec_contribution "funded roles only"
    int is_coordinator
  }
  dim_project {
    bigint project_id PK
    varchar programme_name
    varchar pillar_title
    varchar action_family
    int start_year
    int duration_months
    int consortium_size
  }
  dim_organisation {
    bigint organisation_id PK
    varchar type_label
    varchar country_name
    boolean is_eu27
  }
  bridge_project_domain {
    bigint project_id FK
    varchar domain_code FK
    double weight
  }
```
