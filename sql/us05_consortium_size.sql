-- US05. Consortium size (distinct organisations) and number of countries by type of action (Horizon Europe).
SELECT action_family,
       COUNT(*)                                                    AS projects,
       ROUND(AVG(consortium_size), 1)                              AS avg_members,
       QUANTILE_CONT(consortium_size, 0.5)                         AS median_members,
       ROUND(AVG(n_countries), 1)                                  AS avg_countries,
       ROUND(100.0 * AVG(CASE WHEN consortium_size = 1 THEN 1 ELSE 0 END), 1) AS single_beneficiary_pct
FROM mart.dim_project
WHERE programme_code = 'HORIZON'
GROUP BY action_family
ORDER BY projects DESC;
