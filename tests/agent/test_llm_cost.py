from unittest.mock import MagicMock

from agent.llm_cost import compute_cost, cost_from_response


def test_gpt4o_pricing():
    assert compute_cost("gpt-4o", 1_000_000, 1_000_000) == 12.50


def test_gpt4o_mini_pricing():
    assert compute_cost("gpt-4o-mini", 1_000_000, 1_000_000) == 0.75


def test_unknown_model_costs_nothing():
    assert compute_cost("some-future-model", 1000, 1000) == 0.0


def test_cost_from_response_extracts_usage():
    resp = MagicMock()
    resp.usage.prompt_tokens = 2000
    resp.usage.completion_tokens = 500
    expected = (2000 / 1_000_000) * 0.15 + (500 / 1_000_000) * 0.60
    assert abs(cost_from_response("gpt-4o-mini", resp) - expected) < 1e-9


def test_cost_from_response_missing_usage_returns_zero():
    resp = MagicMock()
    resp.usage = None
    assert cost_from_response("gpt-4o", resp) == 0.0
