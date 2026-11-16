-- Run in CI on a real PostgreSQL server after schema.sql, schema_postgres.sql and mart.sql.
-- Valid rows must load; each invalid row must be rejected (ON_ERROR_STOP is off for the expected failures block).
\set ON_ERROR_STOP on
INSERT INTO framework_programme VALUES ('HORIZON', 'Horizon Europe', 2021, 2027, 'Regulation (EU) 2021/695', NULL);
INSERT INTO programme_part VALUES ('HORIZON.2', 'HORIZON', NULL, 'Pillar II', 1), ('HORIZON.2.5', 'HORIZON', 'HORIZON.2', 'Climate', 2);
INSERT INTO funding_scheme VALUES ('HORIZON-RIA', 'HORIZON', 'Research and innovation action');
INSERT INTO call VALUES ('C1', 'HORIZON');
INSERT INTO topic VALUES ('T1', 'HORIZON', 'Topic');
INSERT INTO load_batch VALUES (1, 'HORIZON', 'https://example.org', NULL, now(), 1, 0, 0);
INSERT INTO country VALUES ('FR', 'FRA', 'FR', 'France', true, NULL);
INSERT INTO organisation_type VALUES ('HES', 'Higher education');
INSERT INTO participant_role VALUES ('coordinator', 'coordinator', true, 'Coordinator'), ('participant', 'beneficiary', true, 'Beneficiary');
INSERT INTO organisation VALUES (111, 'Org A', NULL, 'ORG A', 'HES', 'FR', NULL, NULL, NULL), (222, 'Org B', NULL, 'ORG B', 'HES', 'FR', NULL, NULL, NULL);
INSERT INTO project (project_id, acronym, title, status, programme_code, main_part_code, call_code, topic_code, scheme_code,
                     start_date, end_date, ec_max_contribution, objective, batch_id)
VALUES (1, 'P', 'Project', 'SIGNED', 'HORIZON', 'HORIZON.2.5', 'C1', 'T1', 'HORIZON-RIA', '2024-01-01', '2026-12-31', 100,
        'Hydrogen storage in salt caverns', 1);
INSERT INTO participation (project_id, organisation_id, role_code, order_no, ec_contribution, net_ec_contribution, total_cost, is_sme, has_ended)
VALUES (1, 111, 'coordinator', 1, 60, 60, 60, false, false), (1, 222, 'participant', 2, 40, 40, 40, false, false);
SELECT pillar_title, consortium_size FROM mart.dim_project;
SELECT count(*) AS fts_hits FROM project WHERE to_tsvector('english', objective) @@ to_tsquery('english', 'hydrogen & storage');

-- expected failures: each statement runs in its own transaction and must raise an error
\set ON_ERROR_STOP off
\echo EXPECTED_FAILURES_START
INSERT INTO participation (project_id, organisation_id, role_code, order_no, has_ended) VALUES (1, 222, 'coordinator', 3, false);
INSERT INTO project (project_id, acronym, title, status, programme_code, main_part_code, call_code, topic_code, scheme_code, ec_max_contribution, batch_id)
VALUES (2, 'P', 'P', 'SIGNED', 'HORIZON', 'HORIZON.2.5', 'C1', 'T1', 'HORIZON-RIA', -1, 1);
INSERT INTO participation (project_id, organisation_id, role_code, order_no, has_ended) VALUES (1, 999, 'participant', 4, false);
\echo EXPECTED_FAILURES_END
SELECT count(*) AS participations FROM participation;
