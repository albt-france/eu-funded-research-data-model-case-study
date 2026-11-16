-- =====================================================================================================
-- Analytical variant: a star schema (views) on top of the normalised model.
-- Grain of the fact: one organisation in one project in one role (= one participation row).
-- Why keep both: the 3NF model is the system of record (no redundancy, constraints, easy updates);
-- the star is for reporting (few joins, readable dimensions, additive measures). The star is derived,
-- never edited, so the two can never disagree.
-- Valid in DuckDB and PostgreSQL (recursive CTEs, standard SQL).
-- =====================================================================================================
CREATE SCHEMA mart;

-- programme part -> pillar (top ancestor of the legal-basis hierarchy)
CREATE VIEW mart.dim_programme_part AS
WITH RECURSIVE up AS (
    SELECT part_code, part_code AS ancestor, parent_part_code, depth FROM programme_part
    UNION ALL
    SELECT up.part_code, p.part_code, p.parent_part_code, p.depth
    FROM up JOIN programme_part p ON p.part_code = up.parent_part_code
)
SELECT pp.part_code, pp.programme_code, pp.title, pp.depth,
       top.ancestor AS pillar_code, pil.title AS pillar_title
FROM programme_part pp
JOIN (SELECT part_code, ancestor FROM up WHERE parent_part_code IS NULL) top ON top.part_code = pp.part_code
JOIN programme_part pil ON pil.part_code = top.ancestor;

CREATE VIEW mart.dim_project AS
SELECT p.project_id, p.acronym, p.programme_code, fp.name AS programme_name, p.status,
       p.scheme_code, fs.action_family, dpp.pillar_title, dpp.title AS programme_part_title,
       p.call_code, p.topic_code,
       EXTRACT(YEAR FROM p.start_date) AS start_year,
       (EXTRACT(YEAR FROM p.end_date) - EXTRACT(YEAR FROM p.start_date)) * 12
         + EXTRACT(MONTH FROM p.end_date) - EXTRACT(MONTH FROM p.start_date) + 1 AS duration_months,
       p.ec_max_contribution,
       (SELECT COUNT(DISTINCT x.organisation_id) FROM participation x WHERE x.project_id = p.project_id) AS consortium_size,
       (SELECT COUNT(DISTINCT o.country_code) FROM participation x JOIN organisation o ON o.organisation_id = x.organisation_id
         WHERE x.project_id = p.project_id) AS n_countries
FROM project p
JOIN framework_programme fp ON fp.programme_code = p.programme_code
JOIN funding_scheme fs ON fs.scheme_code = p.scheme_code
JOIN mart.dim_programme_part dpp ON dpp.part_code = p.main_part_code;

CREATE VIEW mart.dim_organisation AS
SELECT o.organisation_id, o.legal_name, o.type_code, ot.label AS type_label, o.country_code,
       c.name AS country_name, c.is_eu27
FROM organisation o
LEFT JOIN organisation_type ot ON ot.type_code = o.type_code
LEFT JOIN country c ON c.country_code = o.country_code;

CREATE VIEW mart.fact_participation AS
SELECT x.participation_id, x.project_id, x.organisation_id, p.programme_code, o.country_code, o.type_code,
       r.role_group, EXTRACT(YEAR FROM p.start_date) AS start_year, x.is_sme,
       -- EU funding counted only for roles that receive it: in 16 Horizon Europe fellowships CORDIS also shows an amount
       -- on the associated partner, while the funded rows already add up to the grant (it would be counted twice)
       CASE WHEN r.receives_eu_funding THEN COALESCE(x.net_ec_contribution, 0) ELSE 0 END AS net_ec_contribution,
       CASE WHEN r.role_group = 'coordinator' THEN 1 ELSE 0 END AS is_coordinator
FROM participation x
JOIN project p ON p.project_id = x.project_id
JOIN organisation o ON o.organisation_id = x.organisation_id
JOIN participant_role r ON r.role_code = x.role_code;

-- bridge project -> top-level scientific domain with an allocation weight (1 / number of top domains of the project),
-- so that funding split by domain adds up to the total instead of being counted once per domain
CREATE VIEW mart.bridge_project_domain AS
WITH tops AS (
    SELECT DISTINCT psd.project_id, '/' || split_part(substr(psd.domain_code, 2), '/', 1) AS top_code
    FROM project_science_domain psd
)
SELECT t.project_id, t.top_code AS domain_code, d.label AS domain_label,
       1.0 / COUNT(*) OVER (PARTITION BY t.project_id) AS weight
FROM tops t JOIN science_domain d ON d.domain_code = t.top_code;
