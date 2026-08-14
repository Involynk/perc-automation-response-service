from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set


# Tier 3 documents to exclude from factual RAG indexing according to Phase 4A
TIER_3_EXCLUDED_FILES: Set[str] = {
    "multi-intent.md",
    "follow-up-contextual.md",
    "ambiguous-incomplete.md",
}


@dataclass
class LoadedDocument:
    """Represents a raw loaded Markdown document with its source metadata."""
    document_id: str
    filename: str
    file_path: Path
    raw_content: str
    tier: int


class DocumentLoader:
    """
    Loads Markdown knowledge documents from a specified directory,
    filtering eligible files according to the PERC Phase 4A classification.
    """
    def __init__(self, directory_path: Path):
        self.directory_path = Path(directory_path)

    def get_tier(self, filename: str) -> int:
        """Determines the document tier based on Phase 4A taxonomy."""
        if filename in TIER_3_EXCLUDED_FILES:
            return 3
        # Tier 1 documents (High structured overlap)
        tier_1_files = {
            "course-discovery.md",
            "course-details.md",
            "fees-pricing.md",
            "eligibility.md",
            "branch-location.md",
            "admission-process.md",
            "availability-status.md",
        }
        if filename in tier_1_files:
            return 1
        return 2  # Tier 2 (Pure Unstructured Knowledge)

    def load_document(self, file_path: Path) -> LoadedDocument:
        """Reads a single Markdown file preserving UTF-8 formatting."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Markdown file not found: {path}")

        filename = path.name
        doc_id = path.stem
        raw_content = path.read_text(encoding="utf-8-sig")
        tier = self.get_tier(filename)

        return LoadedDocument(
            document_id=doc_id,
            filename=filename,
            file_path=path,
            raw_content=raw_content,
            tier=tier,
        )

    def discover_eligible_documents(self, include_tier_3: bool = False) -> List[LoadedDocument]:
        """
        Discovers and loads all eligible Markdown documents in the directory.
        By default, Tier 3 evaluation/scenario files are strictly excluded.
        """
        if not self.directory_path.exists() or not self.directory_path.is_dir():
            raise NotADirectoryError(f"Directory does not exist: {self.directory_path}")

        md_files = sorted(self.directory_path.glob("*.md"))
        loaded_docs: List[LoadedDocument] = []

        for f in md_files:
            tier = self.get_tier(f.name)
            if tier == 3 and not include_tier_3:
                continue
            loaded_docs.append(self.load_document(f))

        return loaded_docs
