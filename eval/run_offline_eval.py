import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv

from agent.nodes.agentic_analyze import agentic_analyze_node
from agent.schemas import AgentState
from eval.golden_dataset import GOLDEN_CASES
from eval.judge import judge_offline_case

load_dotenv()

# Fraction of expected findings the agent must catch across the whole
# dataset for the eval to pass. Tune as the dataset and agent evolve.
PASS_THRESHOLD = 0.7


def _make_synthetic_diff(file: str, content: str) -> str:
    lines = content.splitlines()
    diff_lines = [
        f"diff --git a/{file} b/{file}",
        "new file mode 100644",
        "--- /dev/null",
        f"+++ b/{file}",
        f"@@ -0,0 +1,{len(lines)} @@",
    ]
    diff_lines.extend(f"+{line}" for line in lines)
    return "\n".join(diff_lines)


def run_case(case: dict) -> dict:
    # Tools that touch GitHub (search_similar_bugs) read routing from the
    # process env, not from AgentState -- set it so they behave like a real
    # run instead of erroring on a missing var every time.
    os.environ.setdefault("REPO_FULL_NAME", "eval/golden-dataset")

    with tempfile.TemporaryDirectory() as workspace:
        file_path = Path(workspace) / case["file"]
        file_path.write_text(case["content"], encoding="utf-8")

        state = AgentState(
            diff=_make_synthetic_diff(case["file"], case["content"]),
            changed_files=[case["file"]],
            file_contents={case["file"]: case["content"]},
            workspace=workspace,
            pr_number=0,
            repo_full_name="eval/golden-dataset",
        )

        empty_memory = {"dismissed_fingerprints": {}, "author_notes": {}}
        with patch(
            "agent.nodes.agentic_analyze._load_memory_and_scan_dismissals", return_value=empty_memory
        ), patch(
            # The eval's fake repo_full_name/pr_number make this fail
            # gracefully on its own (no such repo), but don't rely on that:
            # block the side-effecting tool outright during eval.
            "agent.tools.agent_tools.post_comment",
            return_value={"posted": False, "error": "disabled during eval"},
        ):
            result_state = agentic_analyze_node(state)

    verdict = judge_offline_case(case["content"], case["expected_issues"], result_state.issues)

    expected_results = verdict.get("expected_results", [])
    actual_results = verdict.get("actual_results", [])

    return {
        "name": case["name"],
        "issues_found": len(result_state.issues),
        "cost_usd": result_state.cost_usd,
        "caught": sum(1 for r in expected_results if r.get("status") == "caught"),
        "missed": sum(1 for r in expected_results if r.get("status") == "missed"),
        "valid_extra": sum(1 for r in actual_results if r.get("status") == "valid_extra"),
        "false_positives": sum(1 for r in actual_results if r.get("status") == "false_positive"),
    }


def main() -> int:
    results = [run_case(case) for case in GOLDEN_CASES]

    total_expected = sum(r["caught"] + r["missed"] for r in results)
    total_caught = sum(r["caught"] for r in results)
    total_fp = sum(r["false_positives"] for r in results)
    total_reported = sum(r["issues_found"] for r in results)
    total_cost = sum(r["cost_usd"] for r in results)

    recall = total_caught / total_expected if total_expected else 1.0
    fp_rate = total_fp / total_reported if total_reported else 0.0

    print(f"{'case':30s} {'found':>6s} {'caught/expected':>16s} {'false_pos':>10s}")
    for r in results:
        expected_total = r["caught"] + r["missed"]
        print(
            f"{r['name']:30s} {r['issues_found']:>6d} "
            f"{r['caught']}/{expected_total:>13d} {r['false_positives']:>10d}"
        )

    print()
    print(f"Recall (expected issues caught): {recall:.1%}")
    print(f"False positive rate (of all reported): {fp_rate:.1%}")
    print(f"Total eval cost: ${total_cost:.4f}")

    if recall < PASS_THRESHOLD:
        print(f"FAILED: recall {recall:.1%} is below threshold {PASS_THRESHOLD:.0%}")
        return 1

    print("PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
