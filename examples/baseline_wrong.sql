-- known-path generated SQL
-- job: job.revenue_by_region_quarter
-- intent: revenue by region last quarter Finance canonical
-- mode: baseline-naive
-- fact_urn: urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.revenue_old,PROD)
-- fact_name: finance.revenue_old
-- dim_urn: urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.rev_backup,PROD)
-- dim_name: finance.rev_backup

SELECT
  d.region AS region,
  SUM(f.dt) AS revenue
FROM finance.revenue_old AS f
JOIN finance.rev_backup AS d
  ON f.region_id = d.region_id
GROUP BY 1
ORDER BY 2 DESC;

