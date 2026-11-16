-- =====================================================================================================
-- Physical model: EU-funded research projects (CORDIS, Horizon Europe and Horizon 2020)
-- Target: DuckDB (default). The same file is valid PostgreSQL 14+ (checked in CI on a PostgreSQL service);
-- PostgreSQL-only additions (identity, partial index, extended statistics) are in schema_postgres.sql.
-- Normalised to 3NF: every non-key attribute depends on the key, the whole key and nothing but the key.
-- Dialect notes:
--   * DuckDB ignores VARCHAR lengths; PostgreSQL enforces them.
--   * DuckDB checks foreign keys at insert time, including self-references: hierarchies are loaded
--     parent level first (src/load.py). DuckDB does not support ON DELETE CASCADE: deletes are not
--     part of the load (full reload per batch), so none is declared.
--   * COMMENT ON is supported by both; the data dictionary (model/DATA_DICTIONARY.md) is generated
--     from these comments.
-- =====================================================================================================

-- ---------- reference data ----------------------------------------------------------------------------
CREATE TABLE framework_programme (
    programme_code   VARCHAR(16)  PRIMARY KEY,
    name             VARCHAR(100) NOT NULL,
    start_year       SMALLINT     NOT NULL,
    end_year         SMALLINT     NOT NULL,
    legal_act        VARCHAR(100) NOT NULL,
    legal_act_url    VARCHAR(200),
    CONSTRAINT ck_programme_years CHECK (end_year >= start_year)
);

CREATE TABLE programme_part (
    part_code        VARCHAR(40)  PRIMARY KEY,
    programme_code   VARCHAR(16)  NOT NULL REFERENCES framework_programme (programme_code),
    parent_part_code VARCHAR(40)  REFERENCES programme_part (part_code),
    title            VARCHAR(600) NOT NULL,
    depth            SMALLINT     NOT NULL CHECK (depth >= 1)
);

CREATE TABLE country (
    country_code     CHAR(2)      PRIMARY KEY,
    iso3_code        CHAR(3),
    eu_code          VARCHAR(4),
    name             VARCHAR(100) NOT NULL,
    is_eu27          BOOLEAN      NOT NULL,
    authority_uri    VARCHAR(120)
);

CREATE TABLE organisation_type (
    type_code        VARCHAR(3)   PRIMARY KEY,
    label            VARCHAR(80)  NOT NULL
);

CREATE TABLE participant_role (
    role_code        VARCHAR(24)  PRIMARY KEY,
    role_group       VARCHAR(24)  NOT NULL CHECK (role_group IN ('coordinator', 'beneficiary', 'affiliated entity', 'associated partner')),
    receives_eu_funding BOOLEAN   NOT NULL,
    label            VARCHAR(120) NOT NULL
);

CREATE TABLE funding_scheme (
    scheme_code      VARCHAR(40)  PRIMARY KEY,
    programme_code   VARCHAR(16)  NOT NULL REFERENCES framework_programme (programme_code),
    action_family    VARCHAR(40)  NOT NULL
);

CREATE TABLE science_domain (
    domain_code      VARCHAR(80)  PRIMARY KEY,
    notation         VARCHAR(16)  NOT NULL,
    label            VARCHAR(200) NOT NULL,
    parent_code      VARCHAR(80)  REFERENCES science_domain (domain_code),
    depth            SMALLINT     NOT NULL CHECK (depth BETWEEN 1 AND 8),
    euroscivoc_uri   VARCHAR(120)
);

-- ---------- lineage -------------------------------------------------------------------------------------
CREATE TABLE load_batch (
    batch_id         INTEGER      PRIMARY KEY,
    programme_code   VARCHAR(16)  NOT NULL REFERENCES framework_programme (programme_code),
    source_url       VARCHAR(200) NOT NULL,
    downloaded_utc   TIMESTAMP,
    loaded_utc       TIMESTAMP    NOT NULL,
    rows_read        INTEGER      NOT NULL,
    lines_repaired   INTEGER      NOT NULL,
    lines_rejected   INTEGER      NOT NULL
);

-- ---------- calls -----------------------------------------------------------------------------------------
CREATE TABLE call (
    call_code        VARCHAR(60)  PRIMARY KEY,
    programme_code   VARCHAR(16)  NOT NULL REFERENCES framework_programme (programme_code)
);

CREATE TABLE topic (
    topic_code       VARCHAR(80)  PRIMARY KEY,
    programme_code   VARCHAR(16)  NOT NULL REFERENCES framework_programme (programme_code),
    title            VARCHAR(600)
);

-- ---------- projects --------------------------------------------------------------------------------------
CREATE TABLE project (
    project_id          BIGINT        PRIMARY KEY,
    acronym             VARCHAR(60)   NOT NULL,
    title               VARCHAR(600)  NOT NULL,
    status              VARCHAR(12)   NOT NULL CHECK (status IN ('SIGNED', 'CLOSED', 'TERMINATED')),
    programme_code      VARCHAR(16)   NOT NULL REFERENCES framework_programme (programme_code),
    main_part_code      VARCHAR(40)   NOT NULL REFERENCES programme_part (part_code),
    call_code           VARCHAR(60)   NOT NULL REFERENCES call (call_code),
    topic_code          VARCHAR(80)   NOT NULL REFERENCES topic (topic_code),
    scheme_code         VARCHAR(40)   NOT NULL REFERENCES funding_scheme (scheme_code),
    signature_date      DATE,
    start_date          DATE,
    end_date            DATE,
    total_cost          DECIMAL(15,2) CHECK (total_cost > 0),
    ec_max_contribution DECIMAL(15,2) NOT NULL CHECK (ec_max_contribution >= 0),
    grant_doi           VARCHAR(80),
    keywords            VARCHAR(2000),
    objective           TEXT,
    content_update_utc  TIMESTAMP,
    batch_id            INTEGER       NOT NULL REFERENCES load_batch (batch_id),
    CONSTRAINT ck_project_dates CHECK (end_date >= start_date)
);

CREATE TABLE project_programme_part (
    project_id       BIGINT       NOT NULL REFERENCES project (project_id),
    part_code        VARCHAR(40)  NOT NULL REFERENCES programme_part (part_code),
    is_main          BOOLEAN      NOT NULL,
    PRIMARY KEY (project_id, part_code)
);

CREATE TABLE project_science_domain (
    project_id       BIGINT       NOT NULL REFERENCES project (project_id),
    domain_code      VARCHAR(80)  NOT NULL REFERENCES science_domain (domain_code),
    PRIMARY KEY (project_id, domain_code)
);

CREATE TABLE project_document (
    document_id      VARCHAR(40)  PRIMARY KEY,
    project_id       BIGINT       NOT NULL REFERENCES project (project_id),
    doc_type         VARCHAR(40)  NOT NULL,
    url              VARCHAR(600) NOT NULL,
    source           VARCHAR(40)
);

-- Reporting periods are part of every grant agreement but are not published in the CORDIS open data:
-- the table is in the model for the operational system and stays empty here (see docs/analysis/REQUIREMENTS.md).
CREATE TABLE reporting_period (
    project_id       BIGINT       NOT NULL REFERENCES project (project_id),
    period_no        SMALLINT     NOT NULL CHECK (period_no >= 1),
    start_date       DATE         NOT NULL,
    end_date         DATE         NOT NULL,
    report_due_date  DATE,
    PRIMARY KEY (project_id, period_no),
    CONSTRAINT ck_period_dates CHECK (end_date >= start_date)
);

-- ---------- organisations and participations --------------------------------------------------------------
CREATE TABLE organisation (
    organisation_id  BIGINT       PRIMARY KEY,
    legal_name       VARCHAR(400) NOT NULL,
    short_name       VARCHAR(200),
    name_key         VARCHAR(400),
    type_code        VARCHAR(3)   REFERENCES organisation_type (type_code),
    country_code     CHAR(2)      REFERENCES country (country_code),
    city             VARCHAR(120),
    nuts_code        VARCHAR(8),
    website_url      VARCHAR(400)
);

CREATE TABLE participation (
    participation_id    BIGINT        PRIMARY KEY,
    project_id          BIGINT        NOT NULL REFERENCES project (project_id),
    organisation_id     BIGINT        NOT NULL REFERENCES organisation (organisation_id),
    role_code           VARCHAR(24)   NOT NULL REFERENCES participant_role (role_code),
    order_no            SMALLINT      NOT NULL,
    ec_contribution     DECIMAL(15,2) CHECK (ec_contribution >= 0),
    net_ec_contribution DECIMAL(15,2) CHECK (net_ec_contribution >= 0),
    total_cost          DECIMAL(15,2) CHECK (total_cost >= 0),
    is_sme              BOOLEAN,
    has_ended           BOOLEAN       NOT NULL,
    CONSTRAINT uq_participation UNIQUE (project_id, organisation_id, role_code, order_no)
);

-- ---------- indexes (foreign keys used in joins and filters) ----------------------------------------------
CREATE INDEX ix_project_programme    ON project (programme_code);
CREATE INDEX ix_project_topic        ON project (topic_code);
CREATE INDEX ix_project_start        ON project (start_date);
CREATE INDEX ix_participation_proj   ON participation (project_id);
CREATE INDEX ix_participation_org    ON participation (organisation_id);
CREATE INDEX ix_organisation_country ON organisation (country_code);
CREATE INDEX ix_psd_domain           ON project_science_domain (domain_code);
CREATE INDEX ix_document_project     ON project_document (project_id);

-- ---------- descriptions (source of the generated data dictionary) ----------------------------------------
COMMENT ON TABLE framework_programme IS 'An EU research and innovation framework programme (Horizon 2020, Horizon Europe). Source: legal acts.';
COMMENT ON TABLE programme_part IS 'Hierarchy of programme parts from the legal basis (pillar > cluster or programme > ...). Source: CORDIS legalBasis.csv.';
COMMENT ON TABLE country IS 'Country of an organisation, ISO 3166-1 alpha-2. Source: EU Vocabularies country authority table (SPARQL).';
COMMENT ON TABLE organisation_type IS 'CORDIS activity type of an organisation (HES, REC, PRC, PUB, OTH).';
COMMENT ON TABLE participant_role IS 'Role of an organisation in a project; harmonises the H2020 and Horizon Europe role codes into four groups.';
COMMENT ON TABLE funding_scheme IS 'Type of action of a grant (RIA, IA, CSA, ERC, MSCA...). Source: CORDIS project.fundingScheme.';
COMMENT ON TABLE science_domain IS 'EuroSciVoc concept used by CORDIS, with its parent: a tree of scientific domains. Linked to the official EuroSciVoc URI when the notation exists in EU Vocabularies.';
COMMENT ON TABLE load_batch IS 'One load of one CORDIS bundle: lineage for every project row.';
COMMENT ON TABLE call IS 'A call for proposals (CORDIS masterCall).';
COMMENT ON TABLE topic IS 'A call topic: the unit a proposal answers. Source: CORDIS topics.csv.';
COMMENT ON TABLE project IS 'A signed grant (one row per grant agreement). Amounts are the maximum EU contribution, not payments.';
COMMENT ON TABLE project_programme_part IS 'Association project - programme part (a project can draw on several parts; one is the main part).';
COMMENT ON TABLE project_science_domain IS 'Association project - EuroSciVoc domain (many to many).';
COMMENT ON TABLE project_document IS 'Public deliverables and web links of a project. Source: CORDIS webLink.csv.';
COMMENT ON TABLE reporting_period IS 'Reporting periods of a grant agreement. Not published in CORDIS open data: empty in this build.';
COMMENT ON TABLE organisation IS 'A legal entity identified by its Participant Identification Code (PIC). No personal data: address, VAT number and contact form are dropped at ingestion.';
COMMENT ON TABLE participation IS 'An organisation taking part in a project in a role. Grain of the analysis. SME status is stored here because it changes over time.';

COMMENT ON COLUMN project.ec_max_contribution IS 'Maximum EU contribution in the grant agreement (EUR). Commitment, not payment.';
COMMENT ON COLUMN project.total_cost IS 'Total eligible cost (EUR). NULL when CORDIS reports 0 (lump-sum and unit-cost grants do not report it).';
COMMENT ON COLUMN project.status IS 'SIGNED = ongoing, CLOSED = finished, TERMINATED = ended early.';
COMMENT ON COLUMN project.main_part_code IS 'Programme part flagged uniqueProgrammePart = true in CORDIS.';
COMMENT ON COLUMN participation.net_ec_contribution IS 'EU contribution to this organisation net of transfers to affiliated entities (EUR). Measure used in the analysis.';
COMMENT ON COLUMN participation.ec_contribution IS 'EU contribution as reported in CORDIS (EUR); 0 for affiliated entities, NULL in source for associated partners (set to 0).';
COMMENT ON COLUMN participation.is_sme IS 'SME status declared for this participation (it can differ between projects of the same organisation).';
COMMENT ON COLUMN participation.has_ended IS 'True if the organisation left the project (CORDIS endOfParticipation).';
COMMENT ON COLUMN participation.order_no IS 'Position of the participant in the consortium list (CORDIS order).';
COMMENT ON COLUMN organisation.organisation_id IS 'Participant Identification Code (PIC), the EU identifier of a legal entity.';
COMMENT ON COLUMN organisation.name_key IS 'Normalised name (upper case, no accents, punctuation or legal form) used to find duplicate candidates.';
COMMENT ON COLUMN science_domain.domain_code IS 'CORDIS EuroSciVoc path code, e.g. /23/53/373; the last segment is the EuroSciVoc notation.';
