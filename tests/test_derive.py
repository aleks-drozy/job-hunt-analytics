"""Derivers turn free text (private) into coarse enums (exportable).

Rule order matters and is part of the contract: 'Quantitative Developer'
must hit quant before swe's 'developer' keyword; 'AI Software Engineer'
must hit ai_ml before swe's 'engineer'.
"""
import pytest
from job_analytics.derive import role_family, ledger_category


@pytest.mark.parametrize("title,expected", [
    ("Quantitative Developer", "quant"),
    ("Graduate Quant Researcher", "quant"),
    ("AI Software Engineer", "ai_ml"),
    ("Machine Learning Intern", "ai_ml"),
    ("Prompt Engineer", "ai_ml"),
    ("Data Scientist", "ai_ml"),
    ("Data Analyst", "data"),
    ("Analytics Engineer", "data"),
    ("Model Operations (ModelOps) Developer", "data"),
    ("Graduate Software Engineer", "swe"),
    ("Junior Software Developer", "swe"),
    ("Staff Software Engineer, Platform", "swe"),
    ("Project Manager", "pm"),
    ("PMO & Automation Analyst", "pm"),
    ("Delivery Manager", "pm"),
    ("Help Desk Support Specialist", "support_it"),
    ("IT Operations Manager", "support_it"),
    ("Customer Technical Support", "support_it"),
    ("Internal Audit Specialist - IT", "support_it"),
    ("Solutions Architect, Manufacturing", "swe"),
    ("Warehouse Operative", "other"),
])
def test_role_family(title, expected):
    assert role_family(title) == expected


@pytest.mark.parametrize("slug,expected", [
    ("acme-application-status-0712", "job_search"),
    ("followup-wave-batch-two", "job_search"),
    ("cv-render-overflow", "job_search"),
    ("interview-prep-northwind", "job_search"),
    ("bank-feed-heartbeat-gap", "finance"),
    ("weekly-allowance-rebuild", "finance"),
    ("payslip-first-cycle", "finance"),
    ("linkedin-v99-widget-post", "content"),
    ("post-engagement-review", "content"),
    ("widget-tracker-ci-fail", "project"),
    ("repo-release-cut", "project"),
    ("gym-load-vs-nights", "life"),
    ("driving-test-reminder", "life"),
    ("mystery-topic-xyz", "other"),
])
def test_ledger_category(slug, expected):
    assert ledger_category(slug) == expected
