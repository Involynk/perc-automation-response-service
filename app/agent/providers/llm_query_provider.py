from typing import Any, Dict, Optional
import json

from pydantic import BaseModel, ValidationError, Field

from app.schemas.agent import QueryIntent, ExtractedEntities, AmbiguityCheck
from app.core.config import settings
from app.agent.prompts.query_understanding import PROMPT_TEMPLATE


class QueryUnderstandingResultModel(BaseModel):
    primary_intent: QueryIntent
    secondary_intents: Optional[list[QueryIntent]] = Field(default_factory=list)
    entities: Optional[dict] = Field(default_factory=dict)
    ambiguity: Optional[AmbiguityCheck] = Field(default_factory=AmbiguityCheck)
    confidence: float = Field(..., ge=0.0, le=1.0)


class BaseLLMClient:
    """Abstract LLM client interface. Implementations should return a string result."""

    def generate(self, prompt: str) -> str:
        raise NotImplementedError()


class LLMQueryProvider:
    """Production query understanding provider backed by an LLM client.

    The provider expects to receive a client that implements `generate(prompt)` and
    returns a JSON string that matches `QueryUnderstandingResultModel`.
    """

    def __init__(self, client: BaseLLMClient, model_name: Optional[str] = None):
        self.client = client
        self.model_name = model_name or settings.LLM_MODEL

    def analyze(self, query: str, context: Optional[list[dict]] = None) -> Dict[str, Any]:
        # Build a structured prompt instructing the LLM to output JSON only.
        prompt = self._build_prompt(query, context)
        raw = self.client.generate(prompt)

        # Extract JSON from potential markdown code fences or think tags
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

        # Expect the client to return a JSON string; parse and validate.
        try:
            data = json.loads(raw_text)
        except Exception as exc:
            raise ValueError(f"LLM returned non-JSON output: {exc}")

        if not isinstance(data, dict):
            raise ValueError("LLM output must be a JSON object/dict")

        try:
            validated = QueryUnderstandingResultModel(**data)
        except ValidationError as ve:
            raise ValueError(f"LLM output failed validation: {ve}")

        # Return as plain dict matching existing contract
        return {
            "primary_intent": validated.primary_intent.value,
            "secondary_intents": [s.value for s in (validated.secondary_intents or [])],
            "entities": validated.entities or {},
            "ambiguity": (validated.ambiguity.model_dump() if hasattr(validated.ambiguity, 'model_dump') else dict(validated.ambiguity)),
            "confidence": float(validated.confidence),
        }

    def _build_prompt(self, query: str, context: Optional[list[dict]] = None) -> str:
        ctx = json.dumps(context, ensure_ascii=False) if context else "[]"
        prompt = f"{PROMPT_TEMPLATE}\nCONTEXT: {ctx}\nQUERY: {query}\n"
        return prompt


__all__ = ["LLMQueryProvider", "BaseLLMClient", "QueryUnderstandingResultModel"]
