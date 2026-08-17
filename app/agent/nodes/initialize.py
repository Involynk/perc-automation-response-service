from app.schemas.request import ResponseRequest
from app.schemas.agent import AgentState, ExtractedEntities, AmbiguityCheck


def initialize_node(request: ResponseRequest) -> AgentState:
    """Create an initial AgentState from the incoming request.

    This node is deterministic and uses safe defaults for all fields.
    """
    state = AgentState(
        session_id=request.session_id,
        query=request.message,
        entities=ExtractedEntities(),
        ambiguity=AmbiguityCheck(),
    )
    # Ensure metadata exists and note initialization
    state.metadata = dict(state.metadata or {})
    state.metadata["initialized_by"] = "initialize_node"
    return state
