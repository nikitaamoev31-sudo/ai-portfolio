-- Тикет: «Не могу добавить четвёртого мастера»
-- Активные сотрудники против лимита тарифа.
-- at_limit  — нормальное поведение, клиенту предлагаем тариф выше;
-- over_limit — лимит не сработал, это баг: эскалация в разработку.
SELECT c.id AS customer_id,
       c.company,
       p.name                         AS plan,
       p.max_staff,
       COUNT(st.id)                   AS active_staff,
       CASE WHEN COUNT(st.id) > p.max_staff THEN 'over_limit'
            ELSE 'at_limit' END       AS state
FROM helpdesk.customers c
JOIN helpdesk.subscriptions s ON s.customer_id = c.id
JOIN helpdesk.plans p         ON p.id = s.plan_id
JOIN helpdesk.staff st        ON st.customer_id = c.id AND st.is_active
GROUP BY c.id, c.company, p.name, p.max_staff
HAVING COUNT(st.id) >= p.max_staff
ORDER BY state DESC, c.id;
