from typing import Any, Dict, List, Optional
import json

from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.agent.prompts.answer_generation import ANSWER_PROMPT_TEMPLATE
from app.agent.providers.llm_query_provider import BaseLLMClient
from app.agent.providers.ollama_client import OllamaLLMClient
from app.schemas.agent import AgentState


class DraftAnswerModel(BaseModel):
    draft_answer: str = Field(...)
    used_structured: bool = Field(...)
    used_rag: bool = Field(...)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)


class AnswerGenerator:
    def __init__(self, client: Optional[BaseLLMClient] = None):
        if client is not None:
            self.client = client
        else:
            # default to Ollama if configured
            if (settings.LLM_PROVIDER or "").lower() == "ollama":
                self.client = OllamaLLMClient()
            else:
                raise RuntimeError("No LLM client provided for AnswerGenerator; configure LLM_PROVIDER=ollama or inject a client")

    def _build_prompt(self, state: AgentState) -> str:
        # Serialize inputs safely
        structured = [tr.model_dump() if hasattr(tr, 'model_dump') else tr for tr in (state.tool_results or [])]
        rag = [rd.model_dump() if hasattr(rd, 'model_dump') else rd for rd in (state.retrieved_documents or [])]
        result_check = state.result_check.model_dump() if hasattr(state.result_check, 'model_dump') else (state.result_check or {})

        prompt = f"{ANSWER_PROMPT_TEMPLATE}\nINTENT: {state.intent.value if state.intent else None}\nQUERY: {state.query}\nRESULT_CHECK: {json.dumps(result_check, ensure_ascii=False)}\nSTRUCTURED_RESULTS: {json.dumps(structured, ensure_ascii=False)}\nRAG_RESULTS: {json.dumps(rag, ensure_ascii=False)}\n"
        return prompt

    def generate(self, state: AgentState) -> DraftAnswerModel:
        prompt = self._build_prompt(state)
        raw = self.client.generate(prompt)
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception as exc:
            raise ValueError(f"LLM returned non-JSON output during generation: {exc}")

        if not isinstance(data, dict):
            raise ValueError("LLM generation output must be a JSON object")

        try:
            dam = DraftAnswerModel(**data)
        except ValidationError as ve:
            raise ValueError(f"LLM generation output failed validation: {ve}")

        return dam


__all__ = ["AnswerGenerator", "DraftAnswerModel"]
