"""Agent orchestration package for Phase 5A (LangGraph foundation).

This package exposes `build_response_graph()` which now returns a compiled
LangGraph `CompiledStateGraph` that executes the Phase 5A node sequence.
"""
from .graph import build_response_graph

__all__ = ["build_response_graph"]
