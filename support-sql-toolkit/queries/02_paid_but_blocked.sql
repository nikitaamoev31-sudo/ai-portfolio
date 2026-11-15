-- Тикет: «Оплатил, а доступ заблокирован»
-- Клиенты, у которых есть успешная оплата после окончания оплаченного периода,
-- но подписка всё ещё не active — значит, продление не сработало (вебхук оплаты не обработан).
SELECT s.customer_id,
       c.company,
       s.status        AS subscription_status,
       s.paid_until,
       p.provider_txn_id,
       p.amount,
       p.created_at    AS paid_at
FROM helpdesk.subscriptions s
JOIN helpdesk.customers c ON c.id = s.customer_id
JOIN LATERAL (
    SELECT * FROM helpdesk.payments p
    WHERE p.customer_id = s.customer_id
      AND p.status = 'succeeded'
      AND p.created_at::date >= s.paid_until
    ORDER BY p.created_at DESC
    LIMIT 1
) p ON TRUE
WHERE s.status IN ('past_due', 'cancelled');
