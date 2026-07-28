-- sql/09_coverage.sql
-- Instrument coverage: how many days the assistant actually produced a
-- briefing, and the inbox load it was summarizing. Descriptive only.
SELECT COUNT(*) AS n_days,
       MIN(day) AS first_day, MAX(day) AS last_day,
       COUNT(inbox_count) AS n_days_with_inbox_stats,
       SUM(inbox_count) AS total_inbox_msgs,
       SUM(inbox_sensitive) AS total_sensitive_suppressed
FROM debrief_days;
