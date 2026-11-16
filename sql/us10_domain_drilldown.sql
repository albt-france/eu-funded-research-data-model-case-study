-- US10. Drill-down: projects in a domain and all its sub-domains (recursive query on the EuroSciVoc tree),
-- here 'artificial intelligence', Horizon Europe. The SPARQL equivalent is semantic/queries/graph_01_domain_tree.rq.
WITH RECURSIVE sub AS (
    SELECT domain_code FROM science_domain WHERE label = 'artificial intelligence'
    UNION ALL
    SELECT d.domain_code FROM science_domain d JOIN sub ON d.parent_code = sub.domain_code
),
projects AS (
    SELECT DISTINCT psd.project_id FROM project_science_domain psd JOIN sub USING (domain_code)
)
SELECT (SELECT COUNT(*) FROM sub) AS domains_in_subtree,
       COUNT(*) AS projects,
       ROUND(SUM(p.ec_max_contribution) / 1e9, 2) AS eu_contribution_bn
FROM projects JOIN project p USING (project_id)
WHERE p.programme_code = 'HORIZON';
