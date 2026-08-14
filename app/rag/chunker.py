import hashlib
import re
from dataclasses import dataclass
from typing import List, Optional

from app.rag.loader import LoadedDocument


@dataclass
class RawChunk:
    """Represents a raw semantic chunk before database ingestion."""
    chunk_id: str
    document_id: str
    source_file: str
    section: str
    heading: str
    chunk_index: int
    content: str
    token_count: int


class SemanticMarkdownChunker:
    """
    Splits Markdown documents along semantic hierarchy boundaries (H2 / H3 headers),
    preserving Markdown tables, lists, and injecting breadcrumb parent context.
    """
    def __init__(self, target_min_tokens: int = 100, target_max_tokens: int = 450):
        self.target_min_tokens = target_min_tokens
        self.target_max_tokens = target_max_tokens

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Heuristic token estimation (~1.3 words per token)."""
        words = len(text.split())
        return max(1, int(words * 1.3))

    @staticmethod
    def generate_chunk_id(doc_id: str, chunk_index: int, content: str) -> str:
        """Generates a stable, deterministic chunk identifier."""
        content_hash = hashlib.sha256(content.strip().encode("utf-8")).hexdigest()[:10]
        return f"{doc_id}_chk_{chunk_index:03d}_{content_hash}"

    def chunk_document(self, document: LoadedDocument) -> List[RawChunk]:
        """
        Parses Markdown hierarchy:
        H1 -> Document Title
        H2 -> Major Section
        H3 -> Subsection
        """
        lines = document.raw_content.splitlines()
        doc_title = document.document_id.replace("-", " ").title()
        
        # Extract H1 if present before processing
        for line in lines:
            if line.startswith("# ") and not line.startswith("##"):
                doc_title = line[2:].strip()
                break

        chunks: List[RawChunk] = []
        
        current_h2: Optional[str] = None
        current_h3: Optional[str] = None
        current_lines: List[str] = []
        chunk_counter = 0

        def flush_current_chunk():
            nonlocal chunk_counter, current_lines, current_h2, current_h3
            text_body = "\n".join(current_lines).strip()
            if not text_body:
                current_lines = []
                return

            section_name = current_h2 if current_h2 else doc_title
            heading_name = current_h3 if current_h3 else (current_h2 if current_h2 else doc_title)

            # Build breadcrumb header
            breadcrumb_parts = [f"# {doc_title}"]
            if current_h2 and current_h2 != doc_title:
                breadcrumb_parts.append(f"## {current_h2}")
            if current_h3 and current_h3 != current_h2:
                breadcrumb_parts.append(f"### {current_h3}")

            breadcrumb_str = " > ".join(breadcrumb_parts)
            full_chunk_text = f"{breadcrumb_str}\n\n{text_body}"
            tokens = self.estimate_tokens(full_chunk_text)
            chunk_id = self.generate_chunk_id(document.document_id, chunk_counter, full_chunk_text)

            chunks.append(
                RawChunk(
                    chunk_id=chunk_id,
                    document_id=document.document_id,
                    source_file=document.filename,
                    section=section_name,
                    heading=heading_name,
                    chunk_index=chunk_counter,
                    content=full_chunk_text,
                    token_count=tokens,
                )
            )
            chunk_counter += 1
            current_lines = []

        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Check for H1
            if line.startswith("# ") and not line.startswith("##"):
                doc_title = line[2:].strip()
                i += 1
                continue

            # Check for H2 (Major Section boundary)
            if line.startswith("## "):
                flush_current_chunk()
                current_h2 = line[3:].strip()
                current_h3 = None
                i += 1
                continue

            # Check for H3 (Subsection boundary)
            if line.startswith("### "):
                flush_current_chunk()
                current_h3 = line[4:].strip()
                i += 1
                continue

            # Check for Markdown table block (keep entire table intact in current chunk)
            if line.strip().startswith("|"):
                table_lines = []
                while i < len(lines) and (lines[i].strip().startswith("|") or (table_lines and not lines[i].strip())):
                    if lines[i].strip().startswith("|"):
                        table_lines.append(lines[i])
                    i += 1
                current_lines.extend(table_lines)
                continue

            # Ignore standalone markdown horizontal rules '---'
            if line.strip() == "---":
                i += 1
                continue

            current_lines.append(line)
            i += 1

        # Flush any remaining buffer
        flush_current_chunk()

        # If document had no headers, create at least one chunk if content exists
        if not chunks and document.raw_content.strip():
            full_text = f"# {doc_title}\n\n{document.raw_content.strip()}"
            tokens = self.estimate_tokens(full_text)
            chunks.append(
                RawChunk(
                    chunk_id=self.generate_chunk_id(document.document_id, 0, full_text),
                    document_id=document.document_id,
                    source_file=document.filename,
                    section=doc_title,
                    heading=doc_title,
                    chunk_index=0,
                    content=full_text,
                    token_count=tokens,
                )
            )

        return chunks
