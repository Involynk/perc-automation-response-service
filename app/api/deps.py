from typing import Any
from app.agent.graph import build_response_graph


def get_response_graph() -> Any:
    """Dependency provider for the compiled LangGraph response graph.

    Can be overridden in tests via app.dependency_overrides[get_response_graph].
    """
    return build_response_graph()
