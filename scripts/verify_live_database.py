from app.db.session import SessionLocal
from sqlalchemy import text


def verify_tables():
    db = SessionLocal()
    try:
        # 1. Check all resp_* tables
        tables = [
            r[0]
            for r in db.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name LIKE 'resp_%' "
                    "ORDER BY table_name;"
                )
            ).fetchall()
        ]
        print("=== LIVE resp_* TABLES IN SUPABASE POSTGRESQL ===")
        for t in tables:
            cnt = db.execute(text(f"SELECT COUNT(*) FROM {t};")).scalar()
            print(f" - {t:30s} : {cnt} rows")

        # 2. Check resp_knowledge_chunks columns
        print("\n=== COLUMNS IN resp_knowledge_chunks ===")
        cols = db.execute(
            text(
                "SELECT column_name, data_type, udt_name "
                "FROM information_schema.columns "
                "WHERE table_name = 'resp_knowledge_chunks' "
                "ORDER BY ordinal_position;"
            )
        ).fetchall()
        for col, dtype, udt in cols:
            print(f" - {col:20s} : {dtype} ({udt})")

        # 3. Check indexes on resp_knowledge_chunks
        print("\n=== INDEXES ON resp_knowledge_chunks ===")
        indexes = db.execute(
            text(
                "SELECT indexname, indexdef FROM pg_indexes "
                "WHERE tablename = 'resp_knowledge_chunks' "
                "ORDER BY indexname;"
            )
        ).fetchall()
        for idx_name, idx_def in indexes:
            print(f" - {idx_name:45s} -> {idx_def}")

    finally:
        db.close()


if __name__ == "__main__":
    verify_tables()
