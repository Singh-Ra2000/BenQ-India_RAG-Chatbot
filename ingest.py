"""
=============================================================
  RAG Ingestion Pipeline — Portable Projector FAQ Chatbot
  Step 1: Ingest & Parse Documents
=============================================================
Supports: PDF, DOCX, XLSX, CSV, HTML, TXT
Output:   Chunked JSON with metadata, ready for embedding
"""

import os
import json
import hashlib
import re
from pathlib import Path
from datetime import datetime

# ── Install check ──────────────────────────────────────────
# Run: pip install pymupdf python-docx openpyxl beautifulsoup4 pandas tiktoken

import fitz                         # PyMuPDF  → PDFs
import docx                         # python-docx → Word docs
import openpyxl                     # openpyxl  → Excel
import pandas as pd                 # pandas    → CSV / Excel tables
from bs4 import BeautifulSoup       # bs4       → HTML
import tiktoken                     # tiktoken  → token counting

# ──────────────────────────────────────────────────────────
#  CONFIG
# ──────────────────────────────────────────────────────────

CHUNK_SIZE      = 400   # target tokens per chunk
CHUNK_OVERLAP   = 50    # overlap tokens between chunks
OUTPUT_DIR      = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

ENCODER = tiktoken.get_encoding("cl100k_base")   # same as text-embedding-3-small

# Map folder names → persona tags
# Put your files in subfolders named accordingly
PERSONA_MAP = {
    "pre_sales":  "pre_sales",
    "post_sales": "post_sales",
    "retailer":   "retailer",
    "general":    "general",
}


# ──────────────────────────────────────────────────────────
#  PARSERS  (one per file type)
# ──────────────────────────────────────────────────────────

def parse_pdf(filepath: Path) -> str:
    """Extract text from PDF using PyMuPDF (handles multi-column, tables)."""
    doc = fitz.open(str(filepath))
    pages = []
    for page in doc:
        text = page.get_text("text")          # raw text extraction
        text = re.sub(r'\n{3,}', '\n\n', text)  # collapse excessive newlines
        pages.append(text.strip())
    doc.close()
    return "\n\n".join(pages)


def parse_docx(filepath: Path) -> str:
    """Extract text from Word .docx files, preserving paragraph structure."""
    document = docx.Document(str(filepath))
    paragraphs = []
    for para in document.paragraphs:
        if para.text.strip():
            paragraphs.append(para.text.strip())
    # Also extract tables
    for table in document.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells)
            if row_text.strip():
                paragraphs.append(row_text)
    return "\n\n".join(paragraphs)


def parse_xlsx(filepath: Path) -> str:
    """Extract all sheets from Excel as structured text blocks."""
    wb = openpyxl.load_workbook(str(filepath), data_only=True)
    all_sheets = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = []
        for row in ws.iter_rows(values_only=True):
            row_values = [str(cell) if cell is not None else "" for cell in row]
            if any(v.strip() for v in row_values):
                rows.append(" | ".join(row_values))
        if rows:
            all_sheets.append(f"[Sheet: {sheet_name}]\n" + "\n".join(rows))
    return "\n\n".join(all_sheets)


def parse_csv(filepath: Path) -> str:
    """Parse CSV into readable row-by-row text."""
    df = pd.read_csv(filepath)
    lines = []
    for _, row in df.iterrows():
        line = ", ".join(f"{col}: {val}" for col, val in row.items() if pd.notna(val))
        lines.append(line)
    return "\n".join(lines)


def parse_html(filepath: Path) -> str:
    """Strip HTML tags and extract readable text using BeautifulSoup."""
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    # Remove script and style elements
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def parse_txt(filepath: Path) -> str:
    """Read plain text files."""
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        return f.read().strip()


PARSERS = {
    ".pdf":  parse_pdf,
    ".docx": parse_docx,
    ".xlsx": parse_xlsx,
    ".xls":  parse_xlsx,
    ".csv":  parse_csv,
    ".html": parse_html,
    ".htm":  parse_html,
    ".txt":  parse_txt,
}


# ──────────────────────────────────────────────────────────
#  CHUNKER
# ──────────────────────────────────────────────────────────

def count_tokens(text: str) -> int:
    return len(ENCODER.encode(text))


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split text into overlapping token-based chunks.
    Tries to respect sentence boundaries.
    """
    # Split into sentences (simple heuristic)
    sentences = re.split(r'(?<=[.?!])\s+', text)
    chunks = []
    current_chunk = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = count_tokens(sentence)

        # If a single sentence exceeds chunk size, hard-split it
        if sentence_tokens > chunk_size:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_tokens = 0
            # Hard split long sentence by words
            words = sentence.split()
            temp = []
            temp_tokens = 0
            for word in words:
                w_tokens = count_tokens(word)
                if temp_tokens + w_tokens > chunk_size:
                    chunks.append(" ".join(temp))
                    temp = temp[-overlap:] if len(temp) > overlap else temp
                    temp_tokens = count_tokens(" ".join(temp))
                temp.append(word)
                temp_tokens += w_tokens
            if temp:
                current_chunk = temp
                current_tokens = temp_tokens
            continue

        if current_tokens + sentence_tokens > chunk_size:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
            # Keep last N tokens as overlap
            overlap_sentences = []
            overlap_tokens = 0
            for s in reversed(current_chunk):
                t = count_tokens(s)
                if overlap_tokens + t <= overlap:
                    overlap_sentences.insert(0, s)
                    overlap_tokens += t
                else:
                    break
            current_chunk = overlap_sentences + [sentence]
            current_tokens = overlap_tokens + sentence_tokens
        else:
            current_chunk.append(sentence)
            current_tokens += sentence_tokens

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return [c.strip() for c in chunks if c.strip()]


# ──────────────────────────────────────────────────────────
#  METADATA BUILDER
# ──────────────────────────────────────────────────────────

def detect_persona(filepath: Path) -> str:
    """Detect persona tag from parent folder name."""
    for part in filepath.parts:
        if part in PERSONA_MAP:
            return PERSONA_MAP[part]
    return "general"


def detect_doc_type(filepath: Path) -> str:
    """Classify document type from filename keywords."""
    name = filepath.stem.lower()
    if any(k in name for k in ["manual", "guide", "instruction"]):
        return "manual"
    elif any(k in name for k in ["troubleshoot", "error", "fix", "issue"]):
        return "troubleshooting"
    elif any(k in name for k in ["spec", "datasheet", "feature"]):
        return "product_spec"
    elif any(k in name for k in ["faq", "question"]):
        return "faq"
    elif any(k in name for k in ["price", "pricing", "moq", "wholesale"]):
        return "pricing"
    elif any(k in name for k in ["warranty", "return", "policy"]):
        return "policy"
    elif any(k in name for k in ["setup", "install", "connect"]):
        return "setup_guide"
    elif any(k in name for k in ["compare", "comparison", "vs"]):
        return "comparison"
    else:
        return "general"


def extract_model_names(text: str) -> list[str]:
    """
    Extract projector model names from text.
    Customize the pattern to match YOUR model naming convention.
    Examples: PX-100, LumiPro 4K, BrightBox Mini
    """
    pattern = r'\b([A-Z]{1,4}[-\s]?\d{2,4}[A-Za-z]?|[A-Z][a-z]+(?:Pro|Max|Mini|Plus|Ultra|4K|HD)\s?\w*)\b'
    matches = re.findall(pattern, text)
    return list(set(matches)) if matches else []


def make_chunk_id(filepath: Path, chunk_index: int) -> str:
    """Generate a stable unique ID for each chunk."""
    raw = f"{filepath.name}_{chunk_index}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


# ──────────────────────────────────────────────────────────
#  MAIN PIPELINE
# ──────────────────────────────────────────────────────────

def process_file(filepath: Path) -> list[dict]:
    """
    Full pipeline for a single file:
    Parse → Clean → Chunk → Tag metadata → Return records
    """
    ext = filepath.suffix.lower()
    parser = PARSERS.get(ext)

    if not parser:
        print(f"  ⚠️  Skipping unsupported file: {filepath.name}")
        return []

    print(f"  📄 Parsing: {filepath.name}")

    try:
        raw_text = parser(filepath)
    except Exception as e:
        print(f"  ❌ Error parsing {filepath.name}: {e}")
        return []

    if not raw_text.strip():
        print(f"  ⚠️  Empty content in: {filepath.name}")
        return []

    chunks = chunk_text(raw_text)
    persona    = detect_persona(filepath)
    doc_type   = detect_doc_type(filepath)
    models     = extract_model_names(raw_text)

    records = []
    for i, chunk in enumerate(chunks):
        record = {
            "id":           make_chunk_id(filepath, i),
            "text":         chunk,
            "metadata": {
                "source":       filepath.name,
                "source_path":  str(filepath),
                "persona":      persona,       # pre_sales | post_sales | retailer | general
                "doc_type":     doc_type,      # manual | troubleshooting | faq | pricing …
                "model_names":  models,        # projector models mentioned
                "chunk_index":  i,
                "total_chunks": len(chunks),
                "token_count":  count_tokens(chunk),
                "file_type":    ext.lstrip("."),
                "ingested_at":  datetime.utcnow().isoformat() + "Z",
            }
        }
        records.append(record)

    print(f"     ✅ {len(chunks)} chunks created")
    return records


def ingest_folder(folder: Path) -> list[dict]:
    """Recursively process all supported files in a folder."""
    all_records = []
    files = [f for f in folder.rglob("*") if f.is_file() and f.suffix.lower() in PARSERS]

    if not files:
        print(f"\n⚠️  No supported files found in '{folder}'")
        print("    Supported: .pdf .docx .xlsx .csv .html .txt")
        return []

    print(f"\n🚀 Found {len(files)} file(s) in '{folder}'\n{'─'*50}")

    for filepath in files:
        records = process_file(filepath)
        all_records.extend(records)

    return all_records


def save_output(records: list[dict], output_path: Path):
    """Save all chunks to a single JSONL file (one JSON object per line)."""
    with open(output_path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"\n💾 Saved {len(records)} chunks → {output_path}")


def print_summary(records: list[dict]):
    """Print a breakdown of ingested data by persona and doc_type."""
    print(f"\n{'═'*50}")
    print("📊  INGESTION SUMMARY")
    print(f"{'═'*50}")
    print(f"  Total chunks : {len(records)}")

    by_persona = {}
    by_doctype = {}
    for r in records:
        p = r["metadata"]["persona"]
        d = r["metadata"]["doc_type"]
        by_persona[p] = by_persona.get(p, 0) + 1
        by_doctype[d] = by_doctype.get(d, 0) + 1

    print("\n  By Persona:")
    for k, v in sorted(by_persona.items()):
        print(f"    {k:<20} {v:>5} chunks")

    print("\n  By Document Type:")
    for k, v in sorted(by_doctype.items()):
        print(f"    {k:<20} {v:>5} chunks")
    print(f"{'═'*50}\n")


# ──────────────────────────────────────────────────────────
#  ENTRY POINT
# ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # Default: look for a 'documents' folder next to this script
    docs_folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("documents")

    if not docs_folder.exists():
        print(f"❌ Folder not found: '{docs_folder}'")
        print("   Usage: python ingest.py <path_to_documents_folder>")
        print("   Or create a 'documents/' folder with subfolders: pre_sales/, post_sales/, retailer/, general/")
        sys.exit(1)

    records = ingest_folder(docs_folder)

    if records:
        output_path = OUTPUT_DIR / "chunks.jsonl"
        save_output(records, output_path)
        print_summary(records)
        print("✅ Step 1 complete! Your chunks are ready for Step 2 (Embedding).")
    else:
        print("⚠️  No records produced. Check your documents folder.")
