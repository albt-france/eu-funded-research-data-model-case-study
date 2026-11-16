-- US12. SME participation: share of participations declared by SMEs and their share of EU contribution, by programme.
SELECT programme_code,
       ROUND(100.0 * AVG(CASE WHEN is_sme THEN 1 ELSE 0 END), 1) AS sme_participation_pct,
       ROUND(100.0 * SUM(CASE WHEN is_sme THEN net_ec_contribution ELSE 0 END) / SUM(net_ec_contribution), 1) AS sme_funding_pct
FROM mart.fact_participation
GROUP BY programme_code ORDER BY programme_code;
