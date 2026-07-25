-- sql/01_funnel_links.sql
-- Sankey links for the application funnel. Two stages, statuses only --
-- the tracker records no "acknowledged" event, so no such stage exists
-- here (an earlier draft imagined one; the data does not support it).
--
-- employer_closed deliberately conflates closed-before-applying with
-- closed-after-applying: the export cannot reliably distinguish them
-- (a fuzzy applied date exports as null either way). One node, one
-- honest caveat, rather than a split the data cannot back.
--
-- no_response_yet is CENSORED, not "ghosted": these rows are simply
-- still open as of the export's as-of date.
WITH outcomes AS (
  SELECT CASE
           WHEN status IN ('applied', 'rejected') THEN 'submitted'
           WHEN status = 'skipped' THEN 'skipped'
           WHEN status = 'closed' THEN 'employer_closed'
           ELSE 'untracked_outcome'
         END AS stage1,
         status
  FROM applications
)
SELECT 'tracked' AS source, stage1 AS target, COUNT(*) AS value
FROM outcomes GROUP BY stage1
UNION ALL
SELECT 'submitted', CASE WHEN status = 'rejected' THEN 'rejected'
                         ELSE 'no_response_yet' END, COUNT(*)
FROM outcomes WHERE stage1 = 'submitted'
GROUP BY 2
ORDER BY source, target;
