from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.pipeline.nodes.cluster import cluster_node
from app.pipeline.nodes.generate import generate_node
from app.pipeline.nodes.ingest import ingest_node
from app.pipeline.nodes.score import score_node
from app.pipeline.state import PipelineState


def _build() -> StateGraph:
    g = StateGraph(PipelineState)
    g.add_node("ingest", ingest_node)
    g.add_node("cluster", cluster_node)
    g.add_node("score", score_node)
    g.add_node("generate", generate_node)
    g.set_entry_point("ingest")
    g.add_edge("ingest", "cluster")
    g.add_edge("cluster", "score")
    g.add_edge("score", "generate")
    g.add_edge("generate", END)
    return g


_checkpointer = MemorySaver()

pipeline_graph = _build().compile(
    checkpointer=_checkpointer,
    interrupt_before=["generate"],
)
