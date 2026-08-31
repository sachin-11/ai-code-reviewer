from langgraph.graph import END, StateGraph

from agent.nodes.agentic_analyze import agentic_analyze_node
from agent.nodes.fetch import fetch_node
from agent.nodes.fix import fix_node
from agent.nodes.publish import publish_node
from agent.nodes.verify import verify_node
from agent.schemas import AgentState


def _route_after_analyze(state: AgentState) -> str:
    # agentic_analyze_node may already stage patches itself (via its apply_fix
    # tool); fix_node overwrites state.patches rather than merging, so skip it
    # when patches already exist to avoid discarding what analyze staged.
    if state.patches:
        return "verify"
    return "fix" if state.issues else "publish"


def _route_after_fix(state: AgentState) -> str:
    return "verify" if state.patches else "publish"


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("fetch", fetch_node)
    graph.add_node("analyze", agentic_analyze_node)
    graph.add_node("fix", fix_node)
    graph.add_node("verify", verify_node)
    graph.add_node("publish", publish_node)

    graph.set_entry_point("fetch")

    graph.add_edge("fetch", "analyze")

    graph.add_conditional_edges(
        "analyze",
        _route_after_analyze,
        {"fix": "fix", "verify": "verify", "publish": "publish"},
    )

    graph.add_conditional_edges(
        "fix",
        _route_after_fix,
        {"verify": "verify", "publish": "publish"},
    )

    graph.add_edge("verify", "publish")
    graph.add_edge("publish", END)

    return graph.compile()
