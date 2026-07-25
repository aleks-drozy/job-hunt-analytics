-- sql/02_funnel_summary.sql
-- Headline numbers for the stat tiles. n_interviews is COMPUTED so the
-- tile moves the day one lands; as_of is the max date appearing anywhere
-- in the applications data (never the wall clock - reruns on unchanged
-- data must be byte-identical).
SELECT
  COUNT(*) AS n_tracked,
  COUNT(*) FILTER (WHERE status IN ('applied', 'rejected')) AS n_submitted,
  COUNT(*) FILTER (WHERE status = 'rejected') AS n_rejected,
  COUNT(*) FILTER (WHERE status = 'applied') AS n_no_response_yet,
  COUNT(*) FILTER (WHERE status = 'interview') AS n_interviews,
  GREATEST(MAX(applied_date), MAX(status_date), MAX(followup_due)) AS as_of
FROM applications;
