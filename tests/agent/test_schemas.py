import pytest
from pydantic import ValidationError

from agent.schemas import AgentState, Category, Issue, Severity


def test_agent_state_instantiates_empty():
    state = AgentState()
    assert state.repo_lang == "mixed"
    assert state.issues == []
    assert state.cost_usd == 0.0
    assert state.pr_number == 0


def test_issue_requires_confidence_in_range():
    with pytest.raises(ValidationError):
        Issue(
            file="a.py",
            line_start=1,
            line_end=2,
            severity=Severity.HIGH,
            category=Category.BUG,
            title="t",
            description="d",
            suggestion="s",
            confidence=1.5,
        )


def test_issue_title_max_length():
    with pytest.raises(ValidationError):
        Issue(
            file="a.py",
            line_start=1,
            line_end=2,
            severity=Severity.HIGH,
            category=Category.BUG,
            title="x" * 81,
            description="d",
            suggestion="s",
            confidence=0.5,
        )


def test_issue_fixable_defaults_true():
    issue = Issue(
        file="a.py",
        line_start=1,
        line_end=2,
        severity=Severity.LOW,
        category=Category.STYLE,
        title="t",
        description="d",
        suggestion="s",
        confidence=0.5,
    )
    assert issue.fixable is True
