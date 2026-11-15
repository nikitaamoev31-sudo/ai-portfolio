-- Тикет: «Списали деньги два раза!»
-- Ищем двойные списания: два успешных платежа одного клиента на одну сумму с интервалом < 10 минут.
SELECT p1.customer_id,
       c.company,
       p1.amount,
       p1.provider_txn_id AS first_txn,
       p2.provider_txn_id AS duplicate_txn,
       p1.created_at      AS first_at,
       p2.created_at      AS duplicate_at,
       EXTRACT(EPOCH FROM p2.created_at - p1.created_at)::int AS seconds_between
FROM helpdesk.payments p1
JOIN helpdesk.payments p2
  ON p2.customer_id = p1.customer_id
 AND p2.amount = p1.amount
 AND p2.id <> p1.id
 AND p2.created_at > p1.created_at
 AND p2.created_at - p1.created_at < INTERVAL '10 minutes'
JOIN helpdesk.customers c ON c.id = p1.customer_id
WHERE p1.status = 'succeeded' AND p2.status = 'succeeded'
ORDER BY p1.created_at DESC;
