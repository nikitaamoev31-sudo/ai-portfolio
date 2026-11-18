-- Marketing channels: spend vs revenue from customers they brought (ROAS)
WITH revenue AS (
    SELECT c.channel, SUM(i.unit_price * i.qty * (1 - i.returned)) AS revenue,
           COUNT(DISTINCT c.customer_id) AS customers
    FROM customers c
    JOIN orders o ON o.customer_id = c.customer_id
    JOIN order_items i ON i.order_id = o.order_id
    GROUP BY c.channel
),
spend AS (SELECT channel, SUM(spend) AS spend FROM ad_spend GROUP BY channel)
SELECT r.channel,
       r.customers,
       ROUND(s.spend, 2)              AS spend,
       ROUND(r.revenue, 2)            AS revenue,
       ROUND(s.spend / r.customers, 2) AS cac,
       ROUND(r.revenue / s.spend, 2)  AS roas
FROM revenue r JOIN spend s ON s.channel = r.channel
ORDER BY roas DESC;
