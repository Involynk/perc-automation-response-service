import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import SessionLocal
from app.rag.retrieval import KnowledgeRetriever


def run_evaluation():
    db = SessionLocal()
    try:
        retriever = KnowledgeRetriever(db, default_top_k=3, default_min_similarity=0.40)
        cases_file = Path(ROOT_DIR, "tests", "rag", "retrieval_cases.json")
        with open(cases_file, "r", encoding="utf-8") as f:
            cases = json.load(f)

        print("# Phase 4C Retrieval Benchmark Results\n")
        print("| ID | Query | Expected Source(s) | Top Retrieved Source | Mode | Score | Hit@1 | Hit@3 | Status |")
        print("|---|---|---|---|---|---|---|---|---|")

        pos_count = 0
        hit1_count = 0
        hit3_count = 0
        neg_count = 0
        neg_pass_count = 0

        for c in cases:
            q = c["query"]
            exp = c["expected_sources"]
            should_return = c["should_return_results"]
            cid = c.get("course_id")
            bid = c.get("branch_id")

            results = retriever.search(
                query=q,
                mode="hybrid",
                top_k=3,
                min_similarity=0.40,
                course_id=cid,
                branch_id=bid,
            )

            top_src = results[0].source_file if results else "NONE"
            score_str = f"{results[0].relevance_score:.4f}" if results else "N/A"
            retrieved_sources = [d.source_file for d in results]

            if should_return:
                pos_count += 1
                hit1 = any(e in top_src for e in exp)
                hit3 = any(e in s for e in exp for s in retrieved_sources)
                if hit1:
                    hit1_count += 1
                if hit3:
                    hit3_count += 1
                status = "PASS" if hit3 else "FAIL"
                hit1_str = "YES" if hit1 else "NO"
                hit3_str = "YES" if hit3 else "NO"
                exp_str = ", ".join(exp)
                print(f"| {c['id']} | {q} | {exp_str} | {top_src} | Hybrid RRF | {score_str} | {hit1_str} | {hit3_str} | {status} |")
            else:
                neg_count += 1
                neg_pass = len(results) == 0
                if neg_pass:
                    neg_pass_count += 1
                status = "PASS" if neg_pass else "FAIL"
                print(f"| {c['id']} | {q} | NONE (Out-of-Scope) | {top_src} | Hybrid RRF | {score_str} | N/A | N/A | {status} |")

        print("\n## Aggregate Metrics")
        print(f"- **Total Test Cases**: {len(cases)}")
        print(f"- **Positive Cases**: {pos_count}")
        print(f"- **Hit@1 Rate**: {(hit1_count / pos_count) * 100:.1f}% ({hit1_count}/{pos_count})")
        print(f"- **Hit@3 Rate**: {(hit3_count / pos_count) * 100:.1f}% ({hit3_count}/{pos_count})")
        print(f"- **Negative Cases**: {neg_count}")
        print(f"- **Rejection Accuracy**: {(neg_pass_count / neg_count) * 100:.1f}% ({neg_pass_count}/{neg_count})")

    finally:
        db.close()


if __name__ == "__main__":
    run_evaluation()
