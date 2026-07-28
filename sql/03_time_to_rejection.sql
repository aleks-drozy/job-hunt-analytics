-- sql/03_time_to_rejection.sql
-- One row per rejection where BOTH dates exist (day-level; same-day = 0).
-- Rendered as a dot strip: at this n every rejection is a visible point;
-- a histogram would manufacture smoothness the data does not have.
-- Rows with a missing applied_date are excluded and the exclusion is
-- REPORTED via n_excluded_missing_dates (same value on every row - it is
-- a dataset-level fact carried alongside per-row data for the renderer).
WITH rej AS (
  SELECT app_id, tier, channel, sector,
         applied_date, status_date,
         date_diff('day', applied_date, status_date) AS days_to_rejection
  FROM applications WHERE status = 'rejected'
)
SELECT app_id, tier, channel, sector, days_to_rejection,
       (SELECT COUNT(*) FROM rej WHERE applied_date IS NULL
         OR status_date IS NULL) AS n_excluded_missing_dates
FROM rej
WHERE applied_date IS NOT NULL AND status_date IS NOT NULL
ORDER BY days_to_rejection, app_id;
