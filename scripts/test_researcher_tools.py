r"""End-to-end check of the Researcher tools on a few papers.

Usage (from the repo root, Ollama running):
    .venv\Scripts\python scripts\test_researcher_tools.py
    .venv\Scripts\python scripts\test_researcher_tools.py --query "diffusion models image editing" --n 3

Steps: search_arxiv -> index_corpus on the first papers (+ one paper with a broken
PDF link to exercise the abstract fallback) -> sanity query on ChromaDB filtered
by run_id.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import index_corpus, search_arxiv  # noqa: E402
from tools.indexing import embed_texts, get_collection  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default="contrastive learning image representation")
    parser.add_argument("--n", type=int, default=2, help="real papers to index (2-3)")
    parser.add_argument("--run-id", default="test-run")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows console is cp1252
    logging.basicConfig(level=logging.INFO, format="  [%(levelname)s] %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    print(f"\n1) search_arxiv({args.query!r}, max_results=5)")
    t = time.time()
    papers = search_arxiv(args.query, max_results=5)
    print(f"   {len(papers)} papers in {time.time() - t:.1f}s")
    for p in papers:
        print(f"   - {p['arxiv_id']} ({p['year']}) {p['title'][:80]}")
    assert papers, "no papers returned"
    assert set(papers[0]) == {"arxiv_id", "title", "authors", "year", "abstract", "pdf_url"}

    selected = papers[: args.n]
    broken = dict(papers[-1], arxiv_id="test.00001", pdf_url="https://arxiv.org/pdf/does-not-exist")
    print(f"\n2) index_corpus({len(selected)} papers + 1 with a broken PDF link, run_id={args.run_id!r})")
    t = time.time()
    report = index_corpus(selected + [broken], args.run_id)
    print(f"   done in {time.time() - t:.1f}s -> {report}")
    assert "test.00001" in report["fallback_abstract"], "abstract fallback not used"

    print("\n3) ChromaDB check")
    collection = get_collection()
    stored = collection.get(where={"run_id": args.run_id}, include=["metadatas"])
    print(f"   {len(stored['ids'])} chunks stored for run_id={args.run_id!r}")
    assert len(stored["ids"]) == report["chunks"], "chunk count mismatch"
    print(f"   metadata sample: {stored['metadatas'][0]}")

    question = "How does contrastive learning build image representations?"
    hits = collection.query(
        query_embeddings=embed_texts([question], kind="query"),
        n_results=3,
        where={"run_id": args.run_id},
    )
    print(f"   top-3 for {question!r}:")
    for doc, meta, dist in zip(hits["documents"][0], hits["metadatas"][0], hits["distances"][0]):
        print(f"   - [{meta['arxiv_id']} #{meta['chunk_index']}, {meta['source']}, d={dist:.3f}] {doc[:100]}...")
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
