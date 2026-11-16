-- US02. Net EU contribution, participations and coordinations by country (Horizon Europe).
SELECT f.country_code, c.name AS country, c.is_eu27,
       COUNT(*)                                     AS participations,
       SUM(f.is_coordinator)                        AS coordinations,
       ROUND(SUM(f.net_ec_contribution) / 1e9, 3)   AS eu_contribution_bn
FROM mart.fact_participation f
LEFT JOIN country c ON c.country_code = f.country_code
WHERE f.programme_code = 'HORIZON'
GROUP BY f.country_code, c.name, c.is_eu27
ORDER BY eu_contribution_bn DESC, f.country_code;
