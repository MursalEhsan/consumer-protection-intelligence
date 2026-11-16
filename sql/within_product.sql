SELECT month, Product, issue_key, SUM(count) AS issue_count,
       SUM(SUM(count)) OVER (PARTITION BY month, Product) AS product_count,
       1.0 * SUM(count) / SUM(SUM(count)) OVER (PARTITION BY month, Product) AS issue_share
FROM mapped_counts GROUP BY month, Product, issue_key;
