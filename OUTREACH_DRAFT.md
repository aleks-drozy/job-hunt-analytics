# DRAFT — NOT POSTED, for Alex to review

This file collects the outreach copy drafted for this project so it lives
next to the repo it describes. Nothing in this file has been posted,
published, or sent anywhere. Alex reviews, edits, and posts manually.

Full grounding, sourcing, character counts, posting-schedule reasoning, and
prepared replies for likely comments live in the private vault, not in this
repo.

The two LinkedIn drafts cover the same repo from different angles (data
result vs. build/ship process) and are flagged in their own files as
overlapping — space them apart or drop one rather than posting both close
together.

---

## LinkedIn draft A — the data result ("0 interviews")

Status: REVIEW - NOT SENT. Proposed slot: Wednesday 2026-08-12 09:30
(unconfirmed by Alex).

> My AI assistant has been logging my job hunt for a month. The data is not flattering.
>
> 50 applications. 0 interviews.
>
> That is the whole headline. Everything below is how it was produced, and what it does not tell you.
>
> Over the past few weeks I turned that log into an actual pipeline, not just a spreadsheet: private markdown trackers parsed into a local database, anonymised into a public CSV export behind an automated privacy gate, 9 SQL queries, 7 charts, a static page. The gate itself got adversarially tested before I trusted it with anything real: gaps were found and fixed before any of this went public. Meant to read as analyst work with the working shown, not a diary entry.
>
> The paragraph I keep coming back to: LinkedIn shows a 0% rejection rate over 8 applications submitted through it. On a chart sorted by rejection rate, that channel looks like the best one I have got. It is actually the worst outcome available, because nothing came back at all, not a yes, not a no, not even a form rejection. Compare that to Workday: 3 rejections out of 4 applications, a 75% rejection rate, also a tiny sample, but one that at least contains information. A rejection is information. Silence is not.
>
> One honest methods note, because it matters more than it sounds: 28 of the 43 submitted applications are still open, and I counted those as censored, not as ghosted, since 19 days is not long enough to call it either way. Of the 15 rejections, only 10 carry a usable date; those came back 0 to 5 days after applying. The other 5 are excluded from that timing figure and counted as excluded, not silently dropped from the total.
>
> The self incriminating part, because it is the actual differentiator here: reviewing my own work before publishing turned up two real bugs, not stylistic nitpicks. The page's "as of" date had picked up a future, scheduled follow up date, so it was quietly claiming the data was ten days fresher than the last real observation. Separately, the finance parser had been silently returning null for every real entry it touched, since the day I wrote it, and nothing downstream complained. Both fixed before anything shipped, and neither would have been visible from just glancing at the output.
>
> n is 50. This describes one month of one person's job search and nothing more: no channel, no tier, no future application.
>
> CS and Software Engineering graduate (2026), Dublin, looking for software engineering roles.
>
> If you are on the hiring side: when a candidate hears nothing back from your company, is that a rejection, a queue, or something that just got lost?
>
> #dataanalytics #sql #jobsearch #dublin

**First comment (updated — the original blocker is stale, repo is now public):**

> `github.com/aleks-drozy/job-hunt-analytics` — live dashboard: `aleks-drozy.github.io/job-hunt-analytics`. Every number is computed from the committed anonymised CSV export alone; no company name, role title, or euro amount exists anywhere in the pipeline by design.
>
> Every number above is descriptive, not inferential, at this sample size (n=50 tracked applications; the channel breakdown above is n=8 and n=4). The 28 still-open applications are counted as censored, not scored as failures or as "ghosted," because 19 days of data isn't enough to call them either way. Rejections with no usable date are excluded from the timing numbers and counted as excluded, not dropped from the total. Happy to answer anything specific in the comments.

Note: the source draft's original blocker ("this post cannot go out until
Alex decides to publish the repository") is now factually stale — the repo
is public and Pages is live as of 2026-07-29/30. That correction has not
yet been written back into the source vault file.

---

## LinkedIn draft B — the build/ship process

Status: REVIEW - NOT SENT. Proposed slot: Wednesday 2026-08-26 09:30
(unconfirmed by Alex). Already reflects the live URLs correctly, no
blocker.

> I built a full data pipeline and a live public dashboard from a private dataset, in one sitting. Repo to Pages, done.
>
> The dataset is my own job search. The pipeline: private markdown trackers, a local database, an anonymising export step, nine SQL queries, seven charts, a static dashboard. Every stage is a committed, reviewable artifact, not a notebook. Nine SQL files anyone can read and rerun against the public export alone, no private access required.
>
> The privacy gate got attacked on purpose before I trusted it with anything real. An adversarial review of the gate found 8 real defects, each fixed with its own red-before/green-after regression test — 5 leak paths and 3 fail-open defects in the gate's own self-check. The worst leak path was a hand-crafted CSV row with one extra field that could have smuggled a real name past every check, because nothing validated a row's shape against its header. Fixed and reverified before the first export ever existed.
>
> Every piece was built, then separately reviewed by a fresh pass with no memory of writing it, specifically hunting for what I would have missed marking my own homework. Before any of it went public, that process found real bugs. A SQL builder that crashed on any file path with an apostrophe in it. A chart that faked a two pixel gap between bars with a coloured stroke, which only looked right because the background happened to match the stroke colour. A chart label that failed accessibility contrast because I picked the wrong colour formula, 2.8 to 1 instead of the 4.5 to 1 the standard requires. And the one that stung most: the page's "as of" date had quietly picked up a future, scheduled date instead of the last real observation, overstating how current the whole thing was by ten days.
>
> All fixed, all independently reverified against the actual files on disk, not just trusted from a summary, before any of it touched the public repo.
>
> 164 tests passing. Zero external requests on the page itself, it is fully static, generated at build time from the committed data, nothing fetched at runtime, nothing that can silently go stale by pointing at a server that stops responding. Repo and live dashboard both linked below.
>
> The part I keep sitting with: none of those four bugs were exotic, none needed a subtle edge case or a rare input. Every one was the kind of small, ordinary mistake that ships silently in most projects, mine included on plenty of past ones, because nobody adversarially checked their own work before calling it done and moving on. What is the smallest bug in something you shipped that, in hindsight, should have been the easiest one in the world to catch?
>
> #dataengineering #softwareengineering #buildinpublic #python

**First comment:**

> `github.com/aleks-drozy/job-hunt-analytics` — live dashboard: `aleks-drozy.github.io/job-hunt-analytics`. Every number and every chart on that page is generated from the committed, anonymised CSV export in the repo. Nothing on it is fetched live, nothing on it names a real company, no euro amount appears anywhere in the pipeline by design. The full build and review writeup is in the repo's README.

---

## CV bullet (compact variant)

Status: REVIEW - NOT ADDED TO THE CV. Full entry, claim-trace table, and
placement notes are in `CV-BULLET-DRAFT.md` (linked above). URL now
permitted since the repo is public.

> Built a tested DuckDB ETL pipeline (164 tests) that parses messy markdown trackers into an anonymised public CSV export behind a CI-enforced privacy gate whose adversarial review found 8 real defects (5 leak paths, 3 fail-open defects in the gate's own self-check), each closed with its own red-before/green-after regression test, then published 9 SQL analyses over 50 applications as a static dashboard (`aleks-drozy.github.io/job-hunt-analytics`) where every rate appears beside its raw numerator and denominator.
