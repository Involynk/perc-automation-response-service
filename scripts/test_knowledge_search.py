import argparse
from pathlib import Path
import sys

# Ensure repository root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import SessionLocal
from app.rag.retrieval import KnowledgeRetriever


def main():
    parser = argparse.ArgumentParser(
        description="PERC Response Service - Knowledge Retrieval CLI Search Tool"
    )
    parser.add_argument("query", type=str, help="Search query string")
    parser.add_argument(
        "--mode",
        type=str,
        default="hybrid",
        choices=["hybrid", "vector", "keyword"],
        help="Search mode (default: hybrid)",
    )
    parser.add_argument("--top-k", type=int, default=3, help="Maximum results (1-5, default: 3)")
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.70,
        help="Minimum similarity/relevance score threshold (default: 0.70)",
    )
    parser.add_argument("--category", type=str, default=None, help="Filter by category (e.g. C7_REQUIRED_DOCUMENTS)")
    parser.add_argument("--course-id", type=str, default=None, help="Filter by course_id (e.g. perc-ignite)")
    parser.add_argument("--branch-id", type=str, default=None, help="Filter by branch_id (e.g. begur-main)")
    parser.add_argument("--document-type", type=str, default=None, help="Filter by document_type (e.g. policy)")
    parser.add_argument("--source-priority", type=str, default=None, help="Filter by source_priority")

    args = parser.parse_args()

    db = SessionLocal()
    try:
        retriever = KnowledgeRetriever(
            db=db,
            default_top_k=args.top_k,
            default_min_similarity=args.min_score,
        )

        print("==================================================")
        print("    PERC RESPONSE SERVICE - KNOWLEDGE SEARCH     ")
        print("==================================================")
        print(f"Query:        {args.query}")
        print(f"Mode:         {args.mode.upper()}")
        print(f"Top K:        {args.top_k}")
        print(f"Min Score:    {args.min_score}")
        if args.category:
            print(f"Category:     {args.category}")
        if args.course_id:
            print(f"Course ID:    {args.course_id}")
        if args.branch_id:
            print(f"Branch ID:    {args.branch_id}")
        print("--------------------------------------------------")

        results = retriever.search(
            query=args.query,
            mode=args.mode,
            top_k=args.top_k,
            min_similarity=args.min_score,
            category=args.category,
            course_id=args.course_id,
            branch_id=args.branch_id,
            document_type=args.document_type,
            source_priority=args.source_priority,
        )

        if not results:
            print("No relevant knowledge found.")
            return

        print(f"Found {len(results)} relevant chunk(s):\n")
        for idx, doc in enumerate(results, start=1):
            meta = doc.metadata or {}
            print(f"{idx}.")
            print(f"Source:   {doc.source_file}")
            print(f"Section:  {meta.get('section', 'N/A')}")
            print(f"Heading:  {meta.get('heading', 'N/A')}")
            print(f"Category: {meta.get('category', 'N/A')}")
            print(f"Score:    {doc.relevance_score}")
            preview = doc.content.replace("\n", " ")
            if len(preview) > 180:
                preview = preview[:180] + "..."
            print(f"Preview:  {preview}")
            print()

    finally:
        db.close()


if __name__ == "__main__":
    main()
