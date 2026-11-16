-- US03. Share of participations and of EU contribution by organisation type, both programmes.
SELECT f.programme_code, f.type_code, t.label,
       COUNT(*) AS participations,
       ROUND(SUM(f.net_ec_contribution) / 1e9, 2) AS eu_contribution_bn,
       ROUND(100.0 * SUM(f.net_ec_contribution) / SUM(SUM(f.net_ec_contribution)) OVER (PARTITION BY f.programme_code), 1) AS share_pct
FROM mart.fact_participation f
LEFT JOIN organisation_type t ON t.type_code = f.type_code
GROUP BY f.programme_code, f.type_code, t.label
ORDER BY f.programme_code, eu_contribution_bn DESC;
