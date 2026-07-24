"""Free text (private) -> coarse enums (safe to export).

These run on PRIVATE data (real role titles, real ledger slugs) and their
outputs are the only trace that reaches the public export. Keyword tables
are ordered: first match wins, so specific families (quant, ai_ml) are
checked before broad ones (swe). All matching is case-insensitive
substring - titles and slugs are short, curated strings, not prose.
"""

_ROLE_RULES = [
    ("quant", ("quant",)),
    ("ai_ml", ("machine learning", " ml ", "ai ", " ai", "prompt", "data scientist")),
    ("data", ("data analyst", "analytics", "data engineer", "modelops",
              "model operations", "business intelligence")),
    ("pm", ("project manager", "product manager", "pmo", "delivery manager",
            "programme manager", "program manager")),
    ("support_it", ("support", "help desk", "service desk", "it operations",
                    "audit")),
    ("swe", ("software", "developer", "engineer", "swe", "architect",
             "full stack", "backend", "frontend")),
]

_LEDGER_RULES = [
    ("content", ("linkedin", "post", "engagement", "impressions")),
    ("finance", ("bank", "budget", "allowance", "payslip", "money", "savings",
                 "finance", "income", "spend")),
    ("life", ("gym", "judo", "fitness", "recovery", "sleep", "driving",
              "health", "shift", "roster")),
    ("project", ("ci", "repo", "deploy", "release", "bug", "test", "vm",
                 "scaffold", "readme", "publish")),
    ("job_search", ("applic", "cv", "interview", "followup", "follow-up",
                    "recruit", "rejection", "offer", "job", "career",
                    "greenhouse", "workday", "tracker")),
]


def _first_match(text, rules, default):
    lowered = " %s " % text.lower().replace("-", " ")
    for family, keywords in rules:
        for kw in keywords:
            if kw in lowered:
                return family
    return default


def role_family(role_title):
    return _first_match(role_title or "", _ROLE_RULES, "other")


def ledger_category(topic_slug):
    return _first_match(topic_slug or "", _LEDGER_RULES, "other")
