"""`index_corpus`: PDF -> text -> chunks -> embeddings -> ChromaDB.

Plain code (not an LLM tool): it runs after HITL 1, on the corpus approved by
the user.

1. Download each PDF (cache `./cache/pdfs`) and extract its text (cache `./cache/text`).
   If the PDF fails or gives almost no text, fall back to title + abstract.
2. Split into overlapping chunks.
3. Embed with `nomic-embed-text` (Ollama).
4. Upsert into ChromaDB (`./chroma_db`, collection `papers`, cosine distance).

Shared with `retrieve_passages` / `check_citations`: `get_collection()` and
`embed_texts(texts, kind="query")`. nomic-embed-text needs a task prefix:
"search_document: " for chunks, "search_query: " for questions; `embed_texts`
adds it.
"""

from __future__ import annotations

import io
import logging
import re
import unicodedata
from pathlib import Path
from typing import Literal

import chromadb
import ollama
from pypdf import PdfReader

from tools._http import http_get
from tools.arxiv_search import PROJECT_ROOT, arxiv_throttle

logger = logging.getLogger(__name__)
logging.getLogger("pypdf").setLevel(logging.ERROR)  # pypdf warns a lot on odd PDFs

CHROMA_DIR = PROJECT_ROOT / "chroma_db"
PDF_CACHE_DIR = PROJECT_ROOT / "cache" / "pdfs"
TEXT_CACHE_DIR = PROJECT_ROOT / "cache" / "text"
COLLECTION_NAME = "papers"
EMBED_MODEL = "nomic-embed-text"

CHUNK_SIZE = 1500  # characters (~350-400 tokens)
CHUNK_OVERLAP = 200
MIN_PDF_TEXT_CHARS = 1000  # below this the PDF is considered unreadable (scan, error page...)
# pypdf sometimes drops the spaces between words on some layouts ("Whilethemainfocus...").
GLUED_WORD_LEN = 25  # a "word" longer than this is almost surely several glued words
GLUED_WARN_RATIO = 0.02  # share of glued text above which we log a warning
GLUED_MAX_RATIO = 0.25  # above this the text is unusable -> abstract fallback
EMBED_BATCH = 32
PDF_TIMEOUT_S = 60

_PREFIX = {"document": "search_document: ", "query": "search_query: "}


# --------------------------------------------------------------------------- shared helpers

def get_collection() -> chromadb.Collection:
    """Return the persistent ChromaDB collection holding every indexed chunk."""
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        COLLECTION_NAME,
        configuration={"hnsw": {"space": "cosine"}},
        embedding_function=None,  # embeddings are always computed by us, with Ollama
    )


def embed_texts(texts: list[str], kind: Literal["document", "query"] = "document") -> list[list[float]]:
    """Embed texts with nomic-embed-text, adding the prefix nomic expects for `kind`."""
    client = ollama.Client()
    vectors: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = [_PREFIX[kind] + t for t in texts[i : i + EMBED_BATCH]]
        try:
            vectors.extend(client.embed(model=EMBED_MODEL, input=batch).embeddings)
        except (ollama.ResponseError, ConnectionError) as exc:
            raise RuntimeError(
                f"Ollama embedding failed ({exc}). Is Ollama running and "
                f"`ollama pull {EMBED_MODEL}` done?"
            ) from exc
    return [list(v) for v in vectors]


# --------------------------------------------------------------------------- PDF -> text

def _safe_name(arxiv_id: str) -> str:
    # Old-style ids contain a slash, e.g. "hep-th/9901001".
    return arxiv_id.replace("/", "_")


def glued_ratio(text: str) -> float:
    """Share of characters belonging to tokens longer than GLUED_WORD_LEN (glued words)."""
    if not text:
        return 0.0
    glued = sum(len(w) for w in text.split() if len(w) > GLUED_WORD_LEN and "://" not in w)
    return glued / len(text)


def _clean_pdf_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)  # ligatures such as U+FB01 -> "fi"
    text = text.replace("\x00", "")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # re-join hyphenated line breaks
    # Drop the bibliography: noisy for retrieval, and citing it would mean citing
    # papers that are not in the corpus. Only cut if the heading is in the second half.
    match = None
    for match in re.finditer(r"\n\s*(references|bibliography)\s*\n", text, flags=re.IGNORECASE):
        pass
    if match and match.start() > len(text) // 2:
        text = text[: match.start()]
    return " ".join(text.split())


def _download_pdf(paper: dict) -> bytes:
    pdf_file = PDF_CACHE_DIR / f"{_safe_name(paper['arxiv_id'])}.pdf"
    if pdf_file.is_file():
        return pdf_file.read_bytes()
    if not paper.get("pdf_url"):
        raise ValueError("no pdf_url")
    arxiv_throttle()  # same 3 s politeness rule as the API
    data = http_get(paper["pdf_url"], PDF_TIMEOUT_S)
    if not data.startswith(b"%PDF"):
        raise ValueError("response is not a PDF")
    PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    pdf_file.write_bytes(data)
    return data


def _paper_text(paper: dict) -> tuple[str, str]:
    """Return (text, source) where source is "pdf" or "abstract"."""
    text_file = TEXT_CACHE_DIR / f"{_safe_name(paper['arxiv_id'])}.txt"
    if text_file.is_file():
        return text_file.read_text(encoding="utf-8"), "pdf"

    try:
        reader = PdfReader(io.BytesIO(_download_pdf(paper)))
        text = _clean_pdf_text("\n".join(page.extract_text() or "" for page in reader.pages))
        if len(text) < MIN_PDF_TEXT_CHARS:
            raise ValueError(f"only {len(text)} characters extracted")
        ratio = glued_ratio(text)
        if ratio > GLUED_MAX_RATIO:
            raise ValueError(f"{ratio:.0%} of the extracted text has no spaces between words")
        if ratio > GLUED_WARN_RATIO:
            logger.warning(
                "%s: %.1f%% of the PDF text has glued words (pypdf limitation)",
                paper["arxiv_id"], 100 * ratio,
            )
        TEXT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        text_file.write_text(text, encoding="utf-8")
        return text, "pdf"
    except Exception as exc:  # any PDF problem -> abstract fallback (canvas risk #3)
        logger.warning("PDF failed for %s (%s): falling back to abstract", paper["arxiv_id"], exc)
        abstract = " ".join(paper.get("abstract", "").split())
        title = " ".join(paper.get("title", "").split())
        return (f"{title}. {abstract}" if abstract else ""), "abstract"


# --------------------------------------------------------------------------- chunking

def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into ~`size`-character chunks overlapping by ~`overlap` characters.

    Cuts preferably at a sentence end, otherwise at a space, never mid-word.
    """
    text = " ".join(text.split())
    if len(text) <= size:
        return [text] if text else []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            window = text[start:end]
            cut = window.rfind(". ", int(size * 0.6))
            if cut == -1:
                cut = window.rfind(" ", int(size * 0.6))
            if cut != -1:
                end = start + cut + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        next_start = end - overlap
        space = text.find(" ", next_start)
        start = space + 1 if 0 <= space < end else next_start
    return [c for c in chunks if c]


# --------------------------------------------------------------------------- main entry point

def index_corpus(papers: list[dict], run_id: str) -> dict:
    """Index approved papers into ChromaDB for one run.

    Args:
        papers: Paper dicts as returned by `search_arxiv` (needs arxiv_id, title,
            year, abstract, pdf_url).
        run_id: Identifier of the current review run; every chunk is tagged with it
            so `retrieve_passages` can filter on it.

    Returns:
        A report: {"run_id", "indexed": [arxiv_id, ...], "fallback_abstract": [...],
        "failed": [...], "chunks": total number of chunks upserted}.

    Re-running on the same (run_id, paper) replaces that paper's chunks.
    """
    if not run_id or not isinstance(run_id, str):
        raise ValueError("run_id must be a non-empty string")

    collection = get_collection()
    report: dict = {"run_id": run_id, "indexed": [], "fallback_abstract": [], "failed": [], "chunks": 0}

    for paper in papers:
        arxiv_id = paper.get("arxiv_id")
        if not arxiv_id:
            logger.warning("Skipping paper without arxiv_id: %r", paper.get("title"))
            report["failed"].append(paper.get("title", "?"))
            continue

        text, source = _paper_text(paper)
        chunks = chunk_text(text)
        if not chunks:
            logger.warning("No text at all for %s, skipped", arxiv_id)
            report["failed"].append(arxiv_id)
            continue

        title = " ".join(paper.get("title", "").split())
        # The title is embedded with each chunk (context), but only the chunk is stored.
        embeddings = embed_texts([f"{title}\n{c}" for c in chunks], kind="document")

        collection.delete(where={"$and": [{"run_id": run_id}, {"arxiv_id": arxiv_id}]})
        collection.upsert(
            ids=[f"{run_id}:{arxiv_id}:{i}" for i in range(len(chunks))],
            embeddings=embeddings,
            documents=chunks,
            metadatas=[
                {
                    "arxiv_id": arxiv_id,
                    "title": title,
                    "year": int(paper.get("year") or 0),
                    "run_id": run_id,
                    "chunk_index": i,
                    "source": source,
                }
                for i in range(len(chunks))
            ],
        )
        report["indexed"].append(arxiv_id)
        if source == "abstract":
            report["fallback_abstract"].append(arxiv_id)
        report["chunks"] += len(chunks)
        logger.info("Indexed %s: %d chunks from %s", arxiv_id, len(chunks), source)

    return report
