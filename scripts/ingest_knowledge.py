import argparse
import sys
from pathlib import Path

from app.db.session import SessionLocal
from app.rag.embeddings import get_embedding_provider
from app.rag.ingestion import KnowledgeIngestionPipeline


def main():
    parser = argparse.ArgumentParser(description="Ingest unstructured Markdown files into RAG knowledge base.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate ingestion without writing to PostgreSQL.",
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["sentence-transformers", "mock"],
        default="sentence-transformers",
        help="Embedding provider: 'sentence-transformers' (production all-MiniLM-L6-v2) or 'mock' (deterministic testing).",
    )
    parser.add_argument(
        "--unstructured-dir",
        type=str,
        default="MockData/unstructured",
        help="Path to unstructured markdown directory.",
    )
    args = parser.parse_args()

    unstructured_path = Path(args.unstructured_dir)
    if not unstructured_path.exists():
        print(f"Error: Directory not found: {unstructured_path}", file=sys.stderr)
        sys.exit(1)

    print("==================================================")
    print("       PERC RESPONSE SERVICE - RAG INGESTION      ")
    print("==================================================")
    print(f"Source Directory:   {unstructured_path.resolve()}")
    print(f"Execution Mode:     {'DRY RUN (No DB modifications)' if args.dry_run else 'LIVE INGESTION'}")
    print(f"Embedding Provider: {args.provider.upper()} (384 dimensions)")

    try:
        provider = get_embedding_provider(args.provider)
    except Exception as exc:
        print(f"\n[ERROR] Failed to initialize embedding provider '{args.provider}': {exc}", file=sys.stderr)
        sys.exit(1)

    pipeline = KnowledgeIngestionPipeline(
        unstructured_dir=unstructured_path,
        embedding_provider=provider,
    )

    db = None if args.dry_run else SessionLocal()
    try:
        summary = pipeline.run_ingestion(db=db, dry_run=args.dry_run)
        print("\n--- Ingestion Summary ---")
        print(f"Total Markdown Files Discovered: {summary.total_files_discovered}")
        print(f"Eligible Files (Tier 1 & Tier 2): {summary.eligible_files_processed}")
        print(f"Tier 3 Evaluation Files Skipped:  {summary.tier_3_files_skipped}")
        print(f"Total Semantic Chunks Created:    {summary.total_chunks_created}")
        print(f"Estimated Total Tokens:           {summary.total_tokens_estimated}")
        print(f"Embedding Vector Dimension:       {summary.vector_dimension}")
        print(f"Processed / Upserted Chunks:      {summary.upserted_count}")
        print("==================================================")
        print("Status: SUCCESS\n")
    finally:
        if db is not None:
            db.close()


if __name__ == "__main__":
    main()
