-- sql/04_channel_outcomes.sql
-- Outcome mix per application channel. Raw counts are the payload; the
-- rejection_rate column is a convenience and its numerator (n_rejected)
-- and denominator (n_submitted) sit beside it - nobody has to trust a
-- percentage at n this small.
SELECT channel,
       COUNT(*) AS n_total,
       COUNT(*) FILTER (WHERE status IN ('applied','rejected')) AS n_submitted,
       COUNT(*) FILTER (WHERE status = 'rejected') AS n_rejected,
       COUNT(*) FILTER (WHERE status = 'applied') AS n_open,
       COUNT(*) FILTER (WHERE status = 'closed') AS n_closed,
       COUNT(*) FILTER (WHERE status = 'skipped') AS n_skipped,
       COUNT(*) FILTER (WHERE status = 'unknown') AS n_unknown,
       ROUND(COUNT(*) FILTER (WHERE status = 'rejected') * 100.0 /
             NULLIF(COUNT(*) FILTER (WHERE status IN ('applied','rejected')), 0), 1)
         AS rejection_rate
FROM applications
GROUP BY channel
ORDER BY n_total DESC, channel;
