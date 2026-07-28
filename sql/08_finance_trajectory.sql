-- sql/08_finance_trajectory.sql
-- Buffer % of target over time, plus income-change event markers. This
-- is ALL the export knows about money, by design: no amounts ever leave
-- the private database, so there is no "adherence vs EUR/week plan"
-- figure here - that framing died at the privacy boundary and this
-- comment is its tombstone.
SELECT event_date, buffer_pct, income_changed
FROM finance_events
WHERE buffer_pct IS NOT NULL OR income_changed
ORDER BY event_date;
