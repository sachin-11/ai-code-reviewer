import json
from unittest.mock import MagicMock
from unittest.mock import patch as mock_patch

from agent.fingerprint import fingerprint
from agent.nodes.agentic_analyze import agentic_analyze_node
from agent.schemas import AgentState


def _final_response(payload):
    msg = MagicMock()
    msg.tool_calls = None
    msg.content = json.dumps(payload)
    resp = MagicMock()
    resp.choices = [MagicMock(message=msg)]
    resp.usage.prompt_tokens = 100
    resp.usage.completion_tokens = 50
    return resp


def test_previously_dismissed_issue_is_suppressed_even_if_model_reports_it_again():
    dismissed_fp = fingerprint("a.py", "security", "SQL injection")
    payload = {
        "issues": [
            {
                "file": "a.py",
                "line_start": 1,
                "line_end": 1,
                "severity": "critical",
                "category": "security",
                "title": "SQL injection",
                "description": "d",
                "suggestion": "s",
                "confidence": 0.9,
                "fixable": True,
            },
            {
                "file": "b.py",
                "line_start": 1,
                "line_end": 1,
                "severity": "high",
                "category": "bug",
                "title": "Null deref",
                "description": "d",
                "suggestion": "s",
                "confidence": 0.9,
                "fixable": True,
            },
        ],
        "fixed_issue_indexes": [],
    }
    fake_memory = {
        "dismissed_fingerprints": {
            dismissed_fp: {
                "file": "a.py",
                "category": "security",
                "title": "SQL injection",
                "dismissed_by": "alice",
                "dismissed_at": "x",
            }
        },
        "author_notes": {},
    }

    with mock_patch(
        "agent.nodes.agentic_analyze._load_memory_and_scan_dismissals", return_value=fake_memory
    ), mock_patch("agent.nodes.agentic_analyze.get_openai_client") as mock_get_client:
        mock_get_client.return_value.chat.completions.create.side_effect = lambda *a, **k: _final_response(
            payload
        )
        state = AgentState(diff="d", workspace=".", pr_number=1)
        new_state = agentic_analyze_node(state)

    titles = [issue.title for issue in new_state.issues]
    assert "SQL injection" not in titles
    assert "Null deref" in titles


def test_max_iterations_does_not_hang_and_returns_empty():
    def make_tool_call_message():
        tc = MagicMock()
        tc.id = "call_x"
        tc.function.name = "search_codebase"
        tc.function.arguments = json.dumps({"query": "foo"})
        msg = MagicMock()
        msg.tool_calls = [tc]
        msg.content = None
        msg.model_dump = lambda exclude_none=True: {"role": "assistant", "tool_calls": []}
        resp = MagicMock()
        resp.choices = [MagicMock(message=msg)]
        resp.usage.prompt_tokens = 100
        resp.usage.completion_tokens = 50
        return resp

    with mock_patch(
        "agent.nodes.agentic_analyze._load_memory_and_scan_dismissals",
        return_value={"dismissed_fingerprints": {}, "author_notes": {}},
    ), mock_patch("agent.nodes.agentic_analyze.get_openai_client") as mock_get_client:
        mock_get_client.return_value.chat.completions.create.side_effect = (
            lambda *a, **k: make_tool_call_message()
        )
        state = AgentState(diff="d", workspace=".", pr_number=1)
        new_state = agentic_analyze_node(state)

    assert new_state.issues == []
    assert new_state.patches == []


def test_llm_failure_returns_empty_without_crashing():
    with mock_patch(
        "agent.nodes.agentic_analyze._load_memory_and_scan_dismissals",
        return_value={"dismissed_fingerprints": {}, "author_notes": {}},
    ), mock_patch("agent.nodes.agentic_analyze.get_openai_client") as mock_get_client:
        mock_get_client.return_value.chat.completions.create.side_effect = RuntimeError("API down")
        state = AgentState(diff="d", workspace=".", pr_number=1)
        new_state = agentic_analyze_node(state)

    assert new_state.issues == []
    assert new_state.patches == []
