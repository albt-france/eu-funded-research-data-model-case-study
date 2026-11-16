-- US06. Grant size and duration by type of action (Horizon Europe): median maximum EU contribution and months.
SELECT action_family,
       COUNT(*) AS projects,
       ROUND(QUANTILE_CONT(ec_max_contribution, 0.5) / 1e6, 2) AS median_grant_m,
       ROUND(SUM(ec_max_contribution) / 1e9, 2)                AS total_bn,
       QUANTILE_CONT(duration_months, 0.5)                     AS median_months
FROM mart.dim_project
WHERE programme_code = 'HORIZON'
GROUP BY action_family
ORDER BY total_bn DESC;
