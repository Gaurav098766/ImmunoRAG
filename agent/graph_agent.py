"""
L7 — Agentic routing: every retriever becomes a LangGraph tool, and an LLM
(via Groq, tool-calling) decides which tool(s) to call and in what order.

Built as a from-scratch ReAct loop (StateGraph + ToolNode), not the
prebuilt create_react_agent, so the routing behavior is fully inspectable —
the L7 gate requires reading the tool-call trace by hand.

Run interactively:
    uv run python -m agent.graph_agent
"""

from typing import Annotated
from typing_extensions import TypedDict

from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from config import GROQ_API_KEY, GROQ_MODEL
from retrieve.filtered import filtered_search
from retrieve.analytics import analytics_query
from retrieve.live import fetch_adverse_events, fetch_drug_label
from retrieve.graph import find_entity_connections


# ---------------------------------------------------------------------------
# Tools — thin wrappers around each retriever. Docstrings ARE the tool
# descriptions the LLM sees, so they're written to be genuinely
# disambiguating rather than generic ("search papers").
# ---------------------------------------------------------------------------

@tool
def search_literature(
    query: str,
    journal: str = None,
    min_pub_year: int = None,
    section: str = None,
) -> str:
    """
    Search the immunotherapy paper corpus for relevant text passages.
    Use this for conceptual/mechanistic questions — how a drug works, what
    a study found, background on a pathway or cell type. Combines dense
    (semantic) and sparse (exact-term/BM25) search, so it handles both
    "how does PD-1 blockade work" and exact terms like "PD-L1" or an NCT id.
    Optionally filter by journal name, minimum publication year, or section
    (e.g. "results", "discussion") when the question specifies them.
    """
    results = filtered_search(query, journal=journal, min_pub_year=min_pub_year, section=section)
    if not results:
        return "No matching passages found."
    return "\n\n".join(f"[{r['pmcid']} | {r['section']}] {r['text'][:400]}" for r in results)


@tool
def query_analytics(question: str) -> str:
    """
    Answer quantitative/aggregate questions about the papers or trials
    tables — counts, trends over time, top-N rankings, distributions by
    phase/status/sponsor. Use for "how many", "top 5", "trend", "average"
    style questions. Translates the question to SQL and runs it against
    Postgres, so numbers come from the database, not the LLM. Do NOT use
    this for "what does the text say" questions — that's search_literature.
    """
    result = analytics_query(question)
    if result["error"]:
        return f"Could not answer via SQL: {result['error']}"
    rows = result["results"]
    if not rows:
        return f"Query ran ({result['sql']}) but returned no rows."
    return f"SQL: {result['sql']}\nRows ({len(rows)} total, showing up to 15):\n{rows[:15]}"


@tool
def get_adverse_events(drug_name: str) -> str:
    """
    Fetch real-world adverse event reports for a drug from the live openFDA
    API (cached in Redis). Use for side effects, safety signals, or
    reported reactions for a specific named drug. This is LIVE data, not
    the local paper corpus, so it can surface things newer than ingest.
    """
    result = fetch_adverse_events(drug_name)
    reactions = []
    for r in result["results"][:5]:
        for rx in r.get("patient", {}).get("reaction", []):
            name = rx.get("reactionmeddrapt")
            if name:
                reactions.append(name)
    return (f"Drug: {drug_name} | Total reports on file: {result['total_reports']} "
            f"| Sample reported reactions: {reactions}")


@tool
def get_drug_label(drug_name: str) -> str:
    """
    Fetch the official FDA label info (indications and warnings) for a drug
    from the live openFDA API (cached in Redis). Use for "what is X
    approved for" or "official warnings for X" questions about a named drug.
    """
    result = fetch_drug_label(drug_name)
    return f"Drug: {drug_name}\nIndications: {result['indications']}\nWarnings: {result['warnings']}"


@tool
def search_knowledge_graph(entity_name: str) -> str:
    """
    Find known relationships for a named entity (drug, molecular target,
    cell type, or condition) in the knowledge graph extracted from the
    corpus. Use for multi-hop/relational questions — "what targets does X
    act on", "what's connected to Y" — where the answer is a relationship
    rather than a passage or an aggregate number. Entity types in the
    graph: Drug, Target, CellType, Condition.
    """
    connections = find_entity_connections(entity_name)
    if not connections:
        return f"No graph connections found for '{entity_name}'."
    lines = []
    for c in connections:
        arrow = "->" if c["direction"] == "outgoing" else "<-"
        lines.append(f"{c['entity']} {arrow}[{c['relation']}]{arrow} {c['connected_to']} "
                     f"({c['connected_type']}) [source: {c['source_pmcid']}]")
    return "\n".join(lines)


TOOLS = [search_literature, query_analytics, get_adverse_events, get_drug_label, search_knowledge_graph]


# ---------------------------------------------------------------------------
# Graph state + nodes
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


SYSTEM_PROMPT = """You are a cancer immunotherapy research assistant with access to \
five tools spanning a literature corpus, a relational database, live safety data, \
and a knowledge graph. Break down the user's question, decide which tool(s) answer \
it, call them in a sensible order, and only answer once you have enough grounded \
information. For questions spanning multiple angles (e.g. "how does X work AND \
what are its side effects AND what trials study it"), call multiple tools — one \
at a time is fine, you'll see each result before deciding the next call. Always \
cite pmcids, NCT ids, or "live openFDA data" for any specific factual claim. If a \
tool returns nothing useful, say so rather than guessing."""

_llm = None


def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=GROQ_MODEL,
            api_key=GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
            temperature=0,
        ).bind_tools(TOOLS)
    return _llm


def agent_node(state: AgentState) -> dict:
    llm = get_llm()
    messages = state["messages"]
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
    response = llm.invoke(messages)
    return {"messages": [response]}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(TOOLS))

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)  # -> "tools" or END
    graph.add_edge("tools", "agent")  # loop back so the LLM sees tool results

    return graph.compile()


def main():
    app = build_graph()
    print("ImmunoRAG — Agentic Routing (L7)")
    print("Type a question, or 'quit' to exit.\n")

    while True:
        query = input("Query> ").strip()
        if query.lower() in ("quit", "exit"):
            break
        if not query:
            continue

        result = app.invoke({"messages": [("user", query)]})

        print("\n--- Tool call trace ---")
        for msg in result["messages"]:
            if getattr(msg, "tool_calls", None):
                for tc in msg.tool_calls:
                    print(f"  called {tc['name']}({tc['args']})")
            elif msg.__class__.__name__ == "ToolMessage":
                print(f"  <- {msg.name} returned {len(str(msg.content))} chars")

        print("\n--- Final answer ---")
        print(result["messages"][-1].content)
        print()


if __name__ == "__main__":
    main()