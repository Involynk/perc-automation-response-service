from app.db.session import SessionLocal
from sqlalchemy import text


def verify_rag_database():
    db = SessionLocal()
    try:
        print("=== RAG KNOWLEDGE INGESTION VERIFICATION ===")
        
        # 1. Total chunk count
        total_chunks = db.execute(text("SELECT COUNT(*) FROM resp_knowledge_chunks;")).scalar()
        print(f"1. Total Chunks in DB:              {total_chunks} (Expected: 104)")
        assert total_chunks == 104, f"Expected 104 chunks, got {total_chunks}"

        # 2. Distinct chunk IDs
        distinct_ids = db.execute(text("SELECT COUNT(DISTINCT id) FROM resp_knowledge_chunks;")).scalar()
        print(f"2. Distinct Chunk IDs:             {distinct_ids} (No duplicates)")
        assert distinct_ids == 104

        # 3. Non-null embeddings & dimension check
        null_embeddings = db.execute(text("SELECT COUNT(*) FROM resp_knowledge_chunks WHERE embedding IS NULL;")).scalar()
        print(f"3. NULL Embeddings Count:           {null_embeddings} (Expected: 0)")
        assert null_embeddings == 0

        sample_dim = db.execute(text("SELECT vector_dims(embedding) FROM resp_knowledge_chunks LIMIT 1;")).scalar()
        print(f"4. Embedding Vector Dimension:      {sample_dim} (Expected: 384)")
        assert sample_dim == 384

        # 5. Tier 3 documents check
        tier_3_count = db.execute(
            text("SELECT COUNT(*) FROM resp_knowledge_chunks WHERE document_id IN ('multi-intent', 'follow-up-contextual', 'ambiguous-incomplete');")
        ).scalar()
        print(f"5. Tier-3 Chunks Present:          {tier_3_count} (Expected: 0)")
        assert tier_3_count == 0

        # 6. Check course_id mappings
        course_chunks = db.execute(text("SELECT DISTINCT course_id FROM resp_knowledge_chunks WHERE course_id IS NOT NULL ORDER BY course_id;")).fetchall()
        course_ids = [c[0] for c in course_chunks]
        print(f"6. Valid Course IDs Mapped ({len(course_ids)}): {course_ids}")

        # 7. Check branch_id mappings
        branch_chunks = db.execute(text("SELECT DISTINCT branch_id FROM resp_knowledge_chunks WHERE branch_id IS NOT NULL;")).fetchall()
        branch_ids = [b[0] for b in branch_chunks]
        print(f"7. Valid Branch IDs Mapped:         {branch_ids}")

        # 8. Check source priority breakdown
        priorities = db.execute(text("SELECT source_priority, COUNT(*) FROM resp_knowledge_chunks GROUP BY source_priority ORDER BY source_priority;")).fetchall()
        print("8. Source Priority Breakdown:")
        for pri, cnt in priorities:
            print(f"   - {pri:20s}: {cnt} chunks")

        print("\n=== ALL VERIFICATION CHECKS PASSED SUCCESSFULLY ===")
    finally:
        db.close()


if __name__ == "__main__":
    verify_rag_database()
