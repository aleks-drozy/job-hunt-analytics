"""Tests for parse_debriefs.py against fabricated, synthetic debrief fixtures.

All company names, dates, and figures below are invented for testing structural
messiness (section presence, inbox-line phrasing variance, filename edge cases) -
none of it is drawn from the real vault.
"""
from job_analytics.parse_debriefs import parse


def write(tmp_path, name, content):
    (tmp_path / name).write_text(content, encoding="utf-8")


def test_full_file_with_all_sections_and_standard_inbox_line(tmp_path):
    write(
        tmp_path,
        "2026-01-05.md",
        """---
updated: 2026-01-05
---

## 🎯 TODAY'S FOCUS
Ship the widget thing.

## 🚧 Projects & agents
Working on Project Zeta.

## 💼 Job search
Applied to Acme Robotics.

## 🏋️ Life & discipline
Gym done.

## 💰 Finance
Buffer looking fine.

## 💡 Suggestion
Take a walk.

## 📅 Today
Standup at 9.

## 📬 Inbox
17 msgs (0 unread, 0 sensitive)

## 🩺 Health
Slept 7h.

## 📥 Captures
Random idea about Northwind Systems.
""",
    )

    rows = parse(tmp_path)

    assert len(rows) == 1
    row = rows[0]
    assert row["date"] == "2026-01-05"
    assert row["has_focus"] is True
    assert row["has_projects"] is True
    assert row["has_job_search"] is True
    assert row["has_life"] is True
    assert row["has_finance"] is True
    assert row["has_suggestion"] is True
    assert row["has_today"] is True
    assert row["has_inbox"] is True
    assert row["has_health"] is True
    assert row["has_captures"] is True
    assert row["inbox_count"] == 17
    assert row["inbox_unread"] == 0
    assert row["inbox_sensitive"] == 0


def test_partial_file_with_alternate_inbox_phrasing(tmp_path):
    write(
        tmp_path,
        "2026-01-06.md",
        """---
updated: 2026-01-06
---

## 🎯 TODAY'S FOCUS
Interview prep for Northwind Systems.

## 💼 Job search
Follow up with Acme Robotics recruiter.

## 📬 Inbox
10 messages, 0 unread, 1 sensitive
""",
    )

    rows = parse(tmp_path)

    assert len(rows) == 1
    row = rows[0]
    assert row["date"] == "2026-01-06"
    assert row["has_focus"] is True
    assert row["has_job_search"] is True
    assert row["has_projects"] is False
    assert row["has_life"] is False
    assert row["has_finance"] is False
    assert row["has_suggestion"] is False
    assert row["has_today"] is False
    assert row["has_health"] is False
    assert row["has_captures"] is False
    assert row["has_inbox"] is True
    assert row["inbox_count"] == 10
    assert row["inbox_unread"] == 0
    assert row["inbox_sensitive"] == 1


def test_file_missing_inbox_line_yields_null_counts_and_skips_non_date_filenames(tmp_path):
    write(
        tmp_path,
        "2026-01-07.md",
        """---
updated: 2026-01-07
---

## 💰 Finance
Buffer holding at a made-up percentage for Northwind Systems payroll.

## 🩺 Health
Fine.
""",
    )
    # Non-date-like filename mixed into the same directory - must be skipped,
    # not crash the parser.
    write(tmp_path, "README.md", "# Not a debrief\n\nJust notes about Acme Robotics.\n")
    write(tmp_path, "TEMPLATE.md", "---\nupdated: n/a\n---\n\n## 📬 Inbox\nsome text\n")

    rows = parse(tmp_path)

    assert len(rows) == 1
    row = rows[0]
    assert row["date"] == "2026-01-07"
    assert row["has_finance"] is True
    assert row["has_health"] is True
    assert row["has_inbox"] is False
    assert row["inbox_count"] is None
    assert row["inbox_unread"] is None
    assert row["inbox_sensitive"] is None


def test_inbox_line_present_but_unparseable_yields_null_counts(tmp_path):
    write(
        tmp_path,
        "2026-01-08.md",
        """---
updated: 2026-01-08
---

## 📬 Inbox
Cleared everything out today, nothing pending.
""",
    )

    rows = parse(tmp_path)

    assert len(rows) == 1
    row = rows[0]
    assert row["has_inbox"] is True
    assert row["inbox_count"] is None
    assert row["inbox_unread"] is None
    assert row["inbox_sensitive"] is None


def test_inbox_counts_found_on_next_line_when_header_line_is_blank_after(tmp_path):
    # Regression: an earlier version of the skip-blank-lines loop had its
    # `break` outside the `if`, so it only ever inspected exactly one line
    # and could never actually reach a summary sentence sitting past a
    # blank line. This fixture reproduces that shape directly.
    write(
        tmp_path,
        "2026-01-09.md",
        """---
updated: 2026-01-09
---

## 📬 Inbox

12 msgs (2 unread, 1 sensitive)
""",
    )

    rows = parse(tmp_path)

    assert len(rows) == 1
    row = rows[0]
    assert row["has_inbox"] is True
    assert row["inbox_count"] == 12
    assert row["inbox_unread"] == 2
    assert row["inbox_sensitive"] == 1


def test_inbox_counts_not_pulled_from_deep_unrelated_content(tmp_path):
    # The blank-line skip must be bounded: it should not wander past a
    # handful of lines into unrelated body text and misattribute a count
    # that has nothing to do with the Inbox section.
    write(
        tmp_path,
        "2026-01-10.md",
        """---
updated: 2026-01-10
---

## 📬 Inbox


Some unrelated line one.
Some unrelated line two.
99 msgs (99 unread, 99 sensitive) mentioned way later, not the real summary.
""",
    )

    rows = parse(tmp_path)

    assert len(rows) == 1
    row = rows[0]
    assert row["has_inbox"] is True
    assert row["inbox_count"] is None
    assert row["inbox_unread"] is None
    assert row["inbox_sensitive"] is None


def test_date_like_but_invalid_calendar_filename_falls_back_to_frontmatter_updated(tmp_path):
    # "2026-02-30" has the right shape (YYYY-MM-DD) but Feb 30 does not exist,
    # so it does not parse as a real date and should fall back to frontmatter.
    write(
        tmp_path,
        "2026-02-30.md",
        """---
updated: 2026-03-01
---

## 🎯 TODAY'S FOCUS
Catching up after a fabricated calendar glitch.
""",
    )

    rows = parse(tmp_path)

    assert len(rows) == 1
    assert rows[0]["date"] == "2026-03-01"
    assert rows[0]["has_focus"] is True
