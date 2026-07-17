-- known-path generated SQL
-- job: job.revenue_by_region_quarter
-- intent: revenue by region last quarter Finance canonical
-- mode: route-sheet
-- fact_urn: urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.revenue_canonical,PROD)
-- fact_name: finance.revenue_canonical
-- dim_urn: urn:li:dataset:(urn:li:dataPlatform:snowflake,dim.region,PROD)
-- dim_name: dim.region

SELECT
  d.region_name AS region,
  SUM(f.revenue_amount) AS revenue
FROM finance.revenue_canonical AS f
JOIN dim.region AS d
  ON f.region_id = d.region_id
WHERE f.order_date >= DATE_TRUNC('quarter', CURRENT_DATE - INTERVAL '1 quarter')
  AND f.order_date <  DATE_TRUNC('quarter', CURRENT_DATE)
GROUP BY 1
ORDER BY 2 DESC;

