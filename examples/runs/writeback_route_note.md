# known-path route: job.revenue_by_region_quarter (SUCCESS)

mode: known-path
intent: Activate trusted tables for revenue by region last quarter
status: SUCCESS
chosen_urns: ['urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.revenue_canonical,PROD)', 'urn:li:dataset:(urn:li:dataPlatform:snowflake,dim.region,PROD)']
entity_fetches: 2
note: route:job.revenue_by_region_quarter: success urns=urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.revenue_canonical,PROD),urn:li:dataset:(urn:li:dataPlatform:snowflake,dim.region,PROD)
message: Activated 2 node(s); 2 entity fetch(es).

