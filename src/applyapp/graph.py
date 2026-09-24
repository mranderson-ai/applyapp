"""LangGraph wiring for one job: what runs, in what order, and why.

Fetch posting and load seeds start in parallel — they do not depend on each other
and seeds are slow (Drive listing or a local folder walk, plus PDF/xlsx text).
Analyze waits for both. The model for each later step is chosen in llm.py.
Resume is written before the cover letter so the letter can stay shorter and not
re-derive the whole career. Critique may loop back to the writer a bounded number
of times; format/upload never run until that loop exits.

`_bind` closes over Settings because LangGraph nodes only receive state. Compile
once per `applyapp run` and invoke it per queue row.
"""

from collections.abc import Callable

from langgraph.graph import END, START, StateGraph

from applyapp.config import Settings
from applyapp import nodes
from applyapp.state import JobState


def _bind(fn: Callable, settings: Settings) -> Callable:
    def node(state: JobState) -> dict:
        return fn(state, settings)

    node.__name__ = fn.__name__
    return node


def build_job_graph(settings: Settings):
    """Return a compiled graph. Invoke with `{"job": JobRow, "revision_count": 0}`."""

    graph = StateGraph(JobState)
    graph.add_node("fetch_posting", _bind(nodes.fetch_posting, settings))
    graph.add_node("load_seeds", _bind(nodes.load_seeds, settings))
    graph.add_node("analyze", _bind(nodes.analyze, settings))
    graph.add_node("write_resume", _bind(nodes.write_resume, settings))
    graph.add_node("write_cover_letter", _bind(nodes.write_cover_letter, settings))
    graph.add_node("critique", _bind(nodes.critique, settings))
    graph.add_node("format_documents", _bind(nodes.format_documents, settings))
    graph.add_node("upload", _bind(nodes.upload, settings))
    graph.add_node("mark_processed", _bind(nodes.mark_processed, settings))

    graph.add_edge(START, "fetch_posting")
    graph.add_edge(START, "load_seeds")
    graph.add_edge("fetch_posting", "analyze")
    graph.add_edge("load_seeds", "analyze")
    graph.add_edge("analyze", "write_resume")
    graph.add_edge("write_resume", "write_cover_letter")
    graph.add_edge("write_cover_letter", "critique")
    graph.add_conditional_edges(
        "critique",
        nodes.needs_revision,
        {"write_resume": "write_resume", "format_documents": "format_documents"},
    )
    graph.add_edge("format_documents", "upload")
    graph.add_edge("upload", "mark_processed")
    graph.add_edge("mark_processed", END)
    return graph.compile()
