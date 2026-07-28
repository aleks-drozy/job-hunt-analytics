-- sql/06_ops_close_times.sql
-- Days-open per completed op where a close date was recorded. Ops closed
-- without a machine-readable close date (the ledger only sometimes
-- records "CLOSED <date>") are counted in n_done_without_close_date,
-- never silently dropped - at n~59 the exclusions are part of the story.
WITH done AS (SELECT * FROM ledger_ops WHERE status = 'done')
SELECT op_id, category, times_raised,
       date_diff('day', first_raised, close_date) AS days_open,
       (SELECT COUNT(*) FROM done WHERE close_date IS NULL)
         AS n_done_without_close_date
FROM done WHERE close_date IS NOT NULL
ORDER BY days_open, op_id;
