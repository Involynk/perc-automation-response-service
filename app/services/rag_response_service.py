import json
import logging
import re
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.repositories.conversation_history_repository import ConversationHistoryRepository
from app.rag.retrieval import KnowledgeRetriever
from app.schemas.request import ResponseRequest
from app.schemas.response import ResponseResponse

logger = logging.getLogger(__name__)

RAG_SYSTEM_PROMPT = """You are an intelligent, empathetic academic counselor and admissions advisor for PERC (Premier Educational Research & Coaching Institute).

Your goal is to answer student and parent queries accurately, politely, and concisely via WhatsApp messaging.

GUIDELINES:
1. Base your answer strictly on the provided RELEVANT CONTEXT from the PERC knowledge base.
2. Consider the previous CONVERSATION HISTORY to understand context (e.g. if the user says "Cet", look at previous messages to understand what they are asking about CET coaching).
3. Keep the tone professional, welcoming, encouraging, and clear.
4. Format using clean WhatsApp-friendly styling (e.g., bullet points with • or -, bold text with *word*, no complex markdown tables).
5. If the context contains details like courses, eligibility, syllabus, timings, or features, summarize them clearly.
6. If the provided context does not contain enough information to fully answer, answer what is known and invite them to connect with the PERC admissions team.

OUTPUT FORMAT:
You must return a valid JSON object with the following structure:
{
  "answer": "Your friendly, formatted WhatsApp response to the student/parent.",
  "confidence": 0.95
}
"""


class RAGResponseService:
    """
    Direct RAG Response Service.
    1. Fetches conversation history for the lead from PostgreSQL 'conversations' table.
    2. Builds a context-aware query combining past history with the current enquiry.
    3. Converts query into vector embeddings and retrieves relevant knowledge chunks via pgvector / hybrid search.
    4. Passes the retrieved context + conversation history + current enquiry to the LLM agent.
    5. Returns the final generated response and sources.
    """

    def __init__(self, db: Optional[Session] = None):
        self._db = db

    def _get_llm_client(self):
        """Initializes available LLM client (Groq or Ollama)."""
        import os
        api_key = settings.LLM_API_KEY or os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY")
        if api_key:
            try:
                from app.agent.providers.groq_client import GroqClient
                return GroqClient(api_key=api_key)
            except Exception as exc:
                print(f"⚠️ [RAGResponseService] Failed to initialize GroqClient: {exc}", flush=True)

        if provider == "ollama" or settings.OLLAMA_BASE_URL:
            try:
                from app.agent.providers.ollama_client import OllamaLLMClient
                client = OllamaLLMClient(timeout=3)
                if client.health_check():
                    return client
            except Exception as exc:
                logger.debug(f"Ollama local service not reachable: {exc}")

        return None


    def _build_contextual_query(self, current_query: str, history: List[Dict[str, Any]]) -> str:
        """
        Combines past message keywords with current inquiry to handle short/follow-up queries like 'Cet' or 'Fees'.
        """
        if not history:
            return current_query

        # Extract last 3 user/assistant turns
        recent_texts = []
        for msg in history[-4:]:
            content = msg.get("content") or ""
            if isinstance(content, dict):
                content = content.get("text") or content.get("body") or ""
            if content and isinstance(content, str) and content.strip():
                recent_texts.append(content.strip())

        if not recent_texts:
            return current_query

        # If current query is very short (< 15 chars), prepend recent context keywords
        if len(current_query.strip()) < 15:
            combined = " ".join(recent_texts) + " " + current_query
            return combined.strip()

        return current_query

    def generate_response(
        self,
        request: ResponseRequest,
        db: Optional[Session] = None,
    ) -> ResponseResponse:
        """Executes direct RAG response generation flow."""
        session_db = db or self._db
        created_session = False
        if session_db is None:
            session_db = SessionLocal()
            created_session = True

        try:
            # 1. Extract Lead ID and metadata
            meta = request.metadata or {}
            lead_id = meta.get("lead_id")
            if not lead_id:
                # Derive from session_id (e.g. 'lead_ee904daf-...' -> 'ee904daf-...')
                lead_id = request.session_id.replace("lead_", "").replace("whatsapp_", "")

            # 2. Check for conversation history passed directly in request metadata, else fetch from Database
            incoming_history = meta.get("conversation_history") or meta.get("conversationHistory") or meta.get("history")
            db_history = []
            if incoming_history and isinstance(incoming_history, list):
                db_history = incoming_history
            else:
                try:
                    conv_repo = ConversationHistoryRepository(session_db)
                    db_history = conv_repo.get_conversation_history(lead_id)
                except Exception as exc:
                    logger.warning(f"Could not read conversation history from DB ({exc}). Using empty history.")
                    db_history = []

            # Format history for prompt
            formatted_history: List[Dict[str, str]] = []
            for m in db_history:
                if isinstance(m, str):
                    formatted_history.append({"role": "user", "content": m})
                    continue
                direction = m.get("direction") or m.get("role") or "inbound"
                role = "user" if direction in ("inbound", "user") else "assistant"
                content = m.get("content") or m.get("message") or ""
                if isinstance(content, dict):
                    content = content.get("text") or content.get("body") or ""
                if content:
                    formatted_history.append({"role": role, "content": str(content)})

            # 3. Formulate Context-Aware Search Query
            search_query = self._build_contextual_query(request.message, db_history)

            # 4. RAG Retrieval via Vector Search & Hybrid Search
            sources: List[str] = []
            context_blocks: List[str] = []

            try:
                retriever = KnowledgeRetriever(session_db)
                retrieved_docs = retriever.search(query=search_query, mode="hybrid", top_k=3)
                for doc in retrieved_docs:
                    if doc.source_file and doc.source_file not in sources:
                        sources.append(doc.source_file)
                    context_blocks.append(f"--- Document: {doc.source_file} ---\n{doc.content}")
            except Exception as exc:
                logger.warning(f"Database vector retrieval unavailable ({exc}). Using file-based knowledge base.")
                # Fallback: Search local unstructured knowledge documents
                import os
                mock_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "MockData", "unstructured")
                if os.path.exists(mock_dir):
                    q_words = set(re.findall(r"\w+", search_query.lower()))
                    for fname in os.listdir(mock_dir):
                        if fname.endswith(".md"):
                            fpath = os.path.join(mock_dir, fname)
                            try:
                                with open(fpath, "r", encoding="utf-8") as f:
                                    text_content = f.read()
                                if any(w in text_content.lower() for w in q_words if len(w) > 2):
                                    sources.append(fname)
                                    context_blocks.append(f"--- Document: {fname} ---\n{text_content[:1500]}")
                                    if len(sources) >= 3:
                                        break
                            except Exception:
                                pass

            context_text = "\n\n".join(context_blocks) if context_blocks else "General PERC coaching and admissions information."


            # 5. Build LLM Generation Prompt
            prompt = (
                f"{RAG_SYSTEM_PROMPT}\n\n"
                f"RELEVANT CONTEXT FROM PERC KNOWLEDGE BASE:\n{context_text}\n\n"
                f"CONVERSATION HISTORY:\n{json.dumps(formatted_history, ensure_ascii=False, indent=2)}\n\n"
                f"CURRENT STUDENT ENQUIRY:\n\"{request.message}\"\n\n"
                f"JSON RESPONSE:"
            )

            # 6. Call LLM Agent
            llm_client = self._get_llm_client()
            final_answer = ""

            if llm_client is not None:
                try:
                    raw_llm_output = llm_client.generate(prompt)
                    raw_text = raw_llm_output.strip() if isinstance(raw_llm_output, str) else str(raw_llm_output)

                    # Extract JSON from potential code blocks or thinking tags
                    if "<think>" in raw_text and "</think>" in raw_text:
                        raw_text = raw_text.split("</think>", 1)[-1].strip()
                    if "```" in raw_text:
                        lines = raw_text.splitlines()
                        code_lines = [l for l in lines if not l.strip().startswith("```")]
                        raw_text = "\n".join(code_lines).strip()

                    start = raw_text.find("{")
                    end = raw_text.rfind("}")
                    if start != -1 and end != -1 and end > start:
                        raw_text = raw_text[start : end + 1]

                    parsed = json.loads(raw_text)
                    if isinstance(parsed, dict) and "answer" in parsed:
                        final_answer = str(parsed["answer"])
                    elif isinstance(parsed, dict) and "draft_answer" in parsed:
                        final_answer = str(parsed["draft_answer"])
                except Exception as exc:
                    logger.warning(f"LLM generation encountered an error: {exc}. Using grounded context fallback.")

            # Fallback if LLM unavailable or output parsing failed
            if not final_answer:
                if context_blocks:
                    # Synthesize clean summary from top retrieved document
                    first_doc_content = context_blocks[0].split("\n", 1)[-1].strip()
                    final_answer = (
                        f"Hello! Thank you for contacting PERC. Regarding your enquiry:\n\n"
                        f"{first_doc_content[:600]}...\n\n"
                        f"Please feel free to ask if you would like more information on batches, schedules, or admissions!"
                    )
                else:
                    final_answer = (
                        "Hello! Thank you for reaching out to PERC. We offer comprehensive coaching programs for "
                        "CET, JEE, NEET, and foundation courses. How can we help you today?"
                    )


            logger.info(
                f"✅ [DIRECT RAG RESPONSE] session_id={request.session_id} sources={sources} "
                f"answer_len={len(final_answer)}"
            )

            return ResponseResponse(
                session_id=request.session_id,
                answer=final_answer,
                status="success",
                sources=sources,
                clarification_required=False,
                clarification_question=None,
            )
        finally:
            if created_session and session_db is not None:
                session_db.close()


# Global singleton instance for easy import
rag_response_service = RAGResponseService()
