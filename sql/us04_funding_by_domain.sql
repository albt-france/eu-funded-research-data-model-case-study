-- US04. EU contribution by top-level scientific domain (EuroSciVoc), allocated with the bridge weights
-- so that a project classified in two domains is not counted twice. Unclassified projects shown apart.
SELECT p.programme_code, COALESCE(b.domain_label, '(not classified)') AS domain,
       ROUND(SUM(p.ec_max_contribution * COALESCE(b.weight, 1)) / 1e9, 2) AS eu_contribution_bn,
       ROUND(SUM(COALESCE(b.weight, 1)), 0) AS projects_weighted
FROM mart.dim_project p
LEFT JOIN mart.bridge_project_domain b ON b.project_id = p.project_id
GROUP BY p.programme_code, COALESCE(b.domain_label, '(not classified)')
ORDER BY p.programme_code, eu_contribution_bn DESC;
