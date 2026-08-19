from typing import Any, Dict, List, Optional
import json
import logging

from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.agent.prompts.answer_generation import ANSWER_PROMPT_TEMPLATE
from app.agent.providers.llm_query_provider import BaseLLMClient
from app.agent.providers.ollama_client import OllamaLLMClient, OllamaError
from app.agent.composer import ResponseComposer, NormalizedResult
from app.schemas.agent import AgentState, QueryIntent, ToolResult

logger = logging.getLogger(__name__)


class DraftAnswerModel(BaseModel):
    draft_answer: str = Field(...)
    used_structured: bool = Field(default=False)
    used_rag: bool = Field(default=False)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class AnswerGenerator:
    """
    Universal Answer Generator & Orchestrator:
    1. Normalizes facts from AgentState into a structured NormalizedResult.
    2. Uses ResponseComposer to generate clean, concise, WhatsApp-friendly customer responses.
    3. Leverages LLM (Ollama) only when synthesizing complex unstructured multi-document RAG context.
    """

    def __init__(self, client: Optional[BaseLLMClient] = None):
        self.client = client
        self.composer = ResponseComposer()
        if self.client is None and (settings.LLM_PROVIDER or "").lower() == "ollama":
            try:
                self.client = OllamaLLMClient()
            except Exception as exc:
                logger.debug(f"Could not initialize default Ollama client: {exc}")

    @property
    def _active_composer(self) -> ResponseComposer:
        if not hasattr(self, "composer") or self.composer is None:
            self.composer = ResponseComposer()
        return self.composer

    def generate(self, state: AgentState) -> DraftAnswerModel:
        composer = self._active_composer
        # Step 1: Normalize state into clean fact container
        nr = composer.normalize_state(state)

        # Step 2: If structured facts are available or query is deterministic, use ResponseComposer directly
        if nr.structured_data or nr.structured_list or (state.intent in (QueryIntent.AMBIGUOUS_INCOMPLETE, QueryIntent.GRIEVANCE_HUMAN_HANDOFF, QueryIntent.OUT_OF_SCOPE_ESCALATION)):
            composed_text = composer.compose(nr, state=state)
            evidence = []
            if nr.tool_name:
                evidence.append({"source": "STRUCTURED", "id": nr.tool_name, "note": "Verified database facts"})

            return DraftAnswerModel(
                draft_answer=composed_text,
                used_structured=bool(nr.structured_data or nr.structured_list),
                used_rag=False,
                evidence=evidence,
                confidence=1.0,
            )

        # Step 3: If RAG documents are available, compose grounded answer
        if nr.retrieved_documents:
            if self.client is not None:
                try:
                    prompt = self._build_prompt(state)
                    raw = self.client.generate(prompt)

                    raw_text = raw.strip() if isinstance(raw, str) else str(raw)
                    if "<think>" in raw_text and "</think>" in raw_text:
                        raw_text = raw_text.split("</think>", 1)[-1].strip()
                    if "```" in raw_text:
                        lines = raw_text.splitlines()
                        code_lines = []
                        inside = False
                        for line in lines:
                            if line.strip().startswith("```"):
                                inside = not inside
                                continue
                            if inside:
                                code_lines.append(line)
                        if code_lines:
                            raw_text = "\n".join(code_lines).strip()
                    start = raw_text.find("{")
                    end = raw_text.rfind("}")
                    if start != -1 and end != -1 and end > start:
                        raw_text = raw_text[start : end + 1]

                    data = json.loads(raw_text)
                    if isinstance(data, dict):
                        dam = DraftAnswerModel(**data)
                        return dam
                except Exception as exc:
                    logger.debug(f"LLM synthesis skipped/failed ({exc}); using deterministic composer.")

            composed_rag = composer.compose(nr, state=state)
            sources = nr.sources or ["knowledge_base"]
            return DraftAnswerModel(
                draft_answer=composed_rag,
                used_structured=False,
                used_rag=True,
                evidence=[{"source": "RAG", "id": src, "note": "Grounded document excerpt"} for src in sources],
                confidence=0.95,
            )

        # Step 4: No structured data and no RAG documents -> safe fallback
        fallback_text = composer.compose(nr, state=state)
        return DraftAnswerModel(
            draft_answer=fallback_text,
            used_structured=False,
            used_rag=False,
            evidence=[],
            confidence=0.0,
        )

    def _build_prompt(self, state: AgentState) -> str:
        structured = [tr.model_dump() if hasattr(tr, "model_dump") else tr for tr in (state.tool_results or [])]
        rag = [rd.model_dump() if hasattr(rd, "model_dump") else rd for rd in (state.retrieved_documents or [])]
        result_check = state.result_check.model_dump() if hasattr(state.result_check, "model_dump") else (state.result_check or {})

        prompt = (
            f"{ANSWER_PROMPT_TEMPLATE}\n"
            f"INTENT: {state.intent.value if state.intent else None}\n"
            f"QUERY: {state.query}\n"
            f"RESULT_CHECK: {json.dumps(result_check, ensure_ascii=False)}\n"
            f"STRUCTURED_RESULTS: {json.dumps(structured, ensure_ascii=False)}\n"
            f"RAG_RESULTS: {json.dumps(rag, ensure_ascii=False)}\n"
        )
        return prompt


__all__ = ["AnswerGenerator", "DraftAnswerModel"]
