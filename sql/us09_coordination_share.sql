-- US09. Coordinator share by country (Horizon Europe, countries with 1,000+ participations).
-- Single-beneficiary grants (ERC, MSCA fellowships, EIC) make their only participant the coordinator, so the rate
-- is also shown for collaborative actions only (RIA, IA, CSA), where a consortium chooses its coordinator.
SELECT f.country_code, c.name AS country,
       COUNT(*) AS participations, SUM(f.is_coordinator) AS coordinations,
       ROUND(100.0 * SUM(f.is_coordinator) / COUNT(*), 1) AS coordination_rate_pct,
       ROUND(100.0 * SUM(f.is_coordinator) FILTER (WHERE s.action_family IN ('Research and innovation action', 'Innovation action',
             'Coordination and support action'))
             / COUNT(*) FILTER (WHERE s.action_family IN ('Research and innovation action', 'Innovation action',
             'Coordination and support action')), 1) AS collaborative_coordination_rate_pct
FROM mart.fact_participation f
JOIN project p ON p.project_id = f.project_id
JOIN funding_scheme s ON s.scheme_code = p.scheme_code
LEFT JOIN country c ON c.country_code = f.country_code
WHERE f.programme_code = 'HORIZON'
GROUP BY f.country_code, c.name
HAVING COUNT(*) >= 1000
ORDER BY participations DESC;
