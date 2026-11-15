-- KPI сотрудников поддержки: решённые тикеты, медиана первого ответа, доля SLA, средний CSAT.
SELECT a.full_name,
       a.line,
       COUNT(*)                                                      AS resolved_tickets,
       ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (
           ORDER BY EXTRACT(EPOCH FROM t.first_response_at - t.created_at) / 60)::numeric)
                                                                     AS median_first_response_mins,
       ROUND(100.0 * AVG(CASE WHEN t.first_response_at - t.created_at
                                   <= sp.first_response_mins * INTERVAL '1 minute'
                              THEN 1 ELSE 0 END), 1)                 AS sla_met_pct,
       ROUND(AVG(t.csat), 2)                                         AS avg_csat
FROM helpdesk.tickets t
JOIN helpdesk.agents a        ON a.id = t.agent_id
JOIN helpdesk.sla_policies sp ON sp.priority = t.priority
WHERE t.status = 'resolved'
GROUP BY a.full_name, a.line
ORDER BY sla_met_pct DESC;
