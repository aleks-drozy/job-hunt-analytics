-- sql/07_ops_summary.sql
-- The assistant's operational picture by category: volume, open/done
-- mix, and how many times a topic had to be re-raised before resolution.
SELECT category,
       COUNT(*) AS n_total,
       COUNT(*) FILTER (WHERE status = 'done') AS n_done,
       COUNT(*) FILTER (WHERE status = 'open') AS n_open,
       COUNT(*) FILTER (WHERE status = 'snoozed') AS n_snoozed,
       ROUND(AVG(times_raised), 2) AS avg_times_raised,
       MAX(times_raised) AS max_times_raised
FROM ledger_ops GROUP BY category ORDER BY n_total DESC, category;
