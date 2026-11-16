-- US07. Cooperation between countries: number of Horizon Europe projects in which two countries take part together.
WITH pc AS (
    SELECT DISTINCT f.project_id, f.country_code
    FROM mart.fact_participation f
    WHERE f.programme_code = 'HORIZON' AND f.country_code IS NOT NULL
)
SELECT a.country_code AS country_a, b.country_code AS country_b, COUNT(*) AS shared_projects
FROM pc a JOIN pc b ON a.project_id = b.project_id AND a.country_code < b.country_code
GROUP BY a.country_code, b.country_code
ORDER BY shared_projects DESC;
