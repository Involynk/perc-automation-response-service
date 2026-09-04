import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.rag.retrieval import KnowledgeRetriever
from app.rag.embeddings import get_embedding_provider

def main():
    print("Testing Vector Search & Hybrid RAG Retrieval from Supabase Database...")
    db = SessionLocal()
    try:
        provider = get_embedding_provider("sentence-transformers")
        retriever = KnowledgeRetriever(db=db, embedding_provider=provider)

        test_queries = [
            "What courses does PERC offer?",
            "Do you offer any merit scholarships or fee waivers?",
            "How can students travel to PERC campus and is transport available?",
        ]

        for query in test_queries:
            print("\n" + "="*60)
            print(f"QUERY: {query}")
            print("="*60)
            
            results = retriever.search_hybrid(query=query, top_k=3)
            print(f"Retrieved {len(results)} chunks:")
            for idx, res in enumerate(results, 1):
                score_str = f"{res.relevance_score:.4f}" if res.relevance_score is not None else "N/A"
                heading = res.metadata.get("heading", "N/A") if res.metadata else "N/A"
                print(f"\n--- Chunk #{idx} (Score: {score_str}, Source: {res.source_file}) ---")
                print(f"Heading: {heading}")
                print(f"Content:\n{res.content[:250]}...")
    finally:
        db.close()

if __name__ == "__main__":
    main()

