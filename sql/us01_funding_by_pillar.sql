-- US01. EU contribution (maximum grant) and number of projects by programme and pillar.
SELECT programme_code, pillar_title,
       COUNT(*)                              AS projects,
       ROUND(SUM(ec_max_contribution) / 1e9, 2) AS eu_contribution_bn
FROM mart.dim_project
GROUP BY programme_code, pillar_title
ORDER BY programme_code, eu_contribution_bn DESC;
