"""Ten controlled preservation cases (Prompt C §11.5) plus the boundary checks.

Each case is a rewrite that a competent model might plausibly produce; the point
is that the detector catches the ones that changed something they may not.
"""

from natural_flow_rag.preservation import check

SOURCE_NUMBERS = (
    "Set the reader to 250 words per minute, test it for 10 minutes, and increase "
    "it by 25 only when comprehension remains above 80 percent."
)


def test_numbers_survive_a_faithful_rewrite():
    rewrite = (
        "Start the reader at 250 words per minute. Run it for 10 minutes. Raise it "
        "by 25 only while comprehension stays above 80 percent."
    )
    assert check(SOURCE_NUMBERS, rewrite).passed


def test_a_dropped_number_is_caught():
    rewrite = "Set the reader to 250 words per minute and raise it when comprehension holds."
    report = check(SOURCE_NUMBERS, rewrite)
    assert not report.passed
    assert {v.category for v in report.violations} == {"number"}


def test_an_invented_number_is_caught():
    rewrite = (
        "Set the reader to 250 words per minute, test for 10 minutes, raise by 25 "
        "above 80 percent, and never exceed 400."
    )
    report = check(SOURCE_NUMBERS, rewrite)
    assert not report.passed
    assert any("400" in v.found for v in report.violations)


def test_dates_are_preserved():
    source = "The key was rotated on 2026-07-31 and the audit closed on August 1, 2026."
    good = "Key rotation happened on 2026-07-31; the audit closed on August 1, 2026."
    bad = "Key rotation happened on 2026-07-30; the audit closed on August 1, 2026."
    assert check(source, good).passed
    assert not check(source, bad).passed


def test_protected_terms_from_backticks_are_enforced():
    source = "Access is limited by the `OAuth scopes` approved in the `Admin console`."
    good = "The `OAuth scopes` approved in the `Admin console` bound what it can reach."
    bad = "The permissions approved in the settings screen bound what it can reach."
    assert check(source, good).passed
    report = check(source, bad)
    assert not report.passed
    assert {v.category for v in report.violations} >= {"protected_term"}


def test_caller_supplied_protected_terms_are_enforced():
    source = "Domain-wide authority lets the service account impersonate a user."
    rewrite = "Broad access lets the account act as a user."
    report = check(source, rewrite, protected_terms=["domain-wide authority", "service account"])
    assert not report.passed
    assert len([v for v in report.violations if v.category == "protected_term"]) == 2


def test_obligation_may_not_be_weakened():
    source = "The administrator must rotate the exposed key before the service is re-enabled."
    good = "Before the service comes back, the administrator must rotate the exposed key."
    bad = "The administrator should rotate the exposed key before the service is re-enabled."
    assert check(source, good).passed
    report = check(source, bad)
    assert not report.passed
    assert any(v.category == "obligation" for v in report.violations)


def test_certainty_may_not_be_raised():
    source = "The configuration may reduce the risk, but it has not been proven to prevent failure."
    good = "The configuration may reduce the risk. It has not been proven to prevent failure."
    bad = "The configuration prevents the failure."
    assert check(source, good).passed
    report = check(source, bad)
    assert not report.passed
    assert any(v.category == "certainty" for v in report.violations)


def test_proper_names_are_not_dropped():
    source = "In the Admin console, Jessica reviewed the OAuth grant."
    bad = "In the console, the reviewer checked the grant."
    report = check(source, bad)
    assert not report.passed
    assert any(v.category == "name" for v in report.violations)


def test_sentence_initial_capital_is_not_treated_as_a_name():
    source = "Access is constrained. Permissions bound it."
    rewrite = "What it can reach is bounded by the permissions it was given."
    assert check(source, rewrite).passed


def test_report_counts_what_it_checked():
    report = check(SOURCE_NUMBERS, SOURCE_NUMBERS)
    assert report.passed
    assert report.checked["numbers"] == 4
