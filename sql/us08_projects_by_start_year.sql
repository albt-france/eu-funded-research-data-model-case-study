-- US08. Projects and EU contribution by start year, both programmes.
SELECT programme_code, start_year, COUNT(*) AS projects, ROUND(SUM(ec_max_contribution) / 1e9, 2) AS eu_contribution_bn
FROM mart.dim_project
GROUP BY programme_code, start_year
ORDER BY programme_code, start_year;
