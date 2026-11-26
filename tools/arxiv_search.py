"""`search_arxiv`: query the arXiv API, with a disk cache and rate limiting.

- Cache: one JSON file per (query, max_results) in `./cache/arxiv`.
- Rate limit: at least 3 s between two requests to arXiv (API terms of use).
  Cache hits do not wait. `arxiv_throttle()` is shared with the PDF downloads
  of `index_corpus`.
- At most 30 results per call (canvas risk #3).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

from tools._http import http_get

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARXIV_CACHE_DIR = PROJECT_ROOT / "cache" / "arxiv"

API_URL = "https://export.arxiv.org/api/query"
MIN_DELAY_S = 3.0
MAX_RESULTS_CAP = 30
TIMEOUT_S = 30

_ATOM = "{http://www.w3.org/2005/Atom}"
# Raw arXiv syntax (field prefixes or boolean operators) is passed through as is.
_RAW_SYNTAX = re.compile(r"\b(ti|au|abs|co|jr|cat|rn|id|all|submittedDate):|\b(AND|OR|ANDNOT)\b")
_STOPWORDS = {
    "a", "an", "and", "the", "of", "for", "in", "on", "to", "with", "by", "from",
    "at", "as", "or", "is", "are", "using", "via", "based",
}

_throttle_lock = threading.Lock()
_last_request = 0.0


def arxiv_throttle() -> None:
    """Block until at least `MIN_DELAY_S` seconds have passed since the last arXiv request."""
    global _last_request
    with _throttle_lock:
        wait = MIN_DELAY_S - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()


def _build_search_query(query: str) -> str:
    """Turn free text into an arXiv query: every meaningful word must match (AND).

    "contrastive learning for image representation"
    -> "all:contrastive AND all:learning AND all:image AND all:representation"
    Quoted phrases are kept: '"vision transformer" pruning'
    -> 'all:"vision transformer" AND all:pruning'
    """
    if _RAW_SYNTAX.search(query):
        return query
    terms = re.findall(r'"[^"]+"|[\w\-]+', query)
    terms = [t for t in terms if t.startswith('"') or t.lower() not in _STOPWORDS]
    if not terms:
        terms = [query]
    return " AND ".join(f"all:{t}" for t in terms)


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _parse_feed(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    papers = []
    for entry in root.findall(f"{_ATOM}entry"):
        raw_id = entry.findtext(f"{_ATOM}id", "")
        if "/abs/" not in raw_id:
            # arXiv returns a single "Error" entry for malformed queries.
            raise ValueError(f"arXiv error: {_clean(entry.findtext(f'{_ATOM}summary'))}")
        arxiv_id = re.sub(r"v\d+$", "", raw_id.split("/abs/", 1)[1])

        pdf_url = ""
        for link in entry.findall(f"{_ATOM}link"):
            if link.get("title") == "pdf":
                pdf_url = link.get("href", "")
        pdf_url = (pdf_url or f"https://arxiv.org/pdf/{arxiv_id}").replace("http://", "https://", 1)

        published = entry.findtext(f"{_ATOM}published", "")
        papers.append({
            "arxiv_id": arxiv_id,
            "title": _clean(entry.findtext(f"{_ATOM}title")),
            "authors": [_clean(a.findtext(f"{_ATOM}name")) for a in entry.findall(f"{_ATOM}author")],
            "year": int(published[:4]) if published[:4].isdigit() else 0,
            "abstract": _clean(entry.findtext(f"{_ATOM}summary")),
            "pdf_url": pdf_url,
        })
    return papers


def _fetch(search_query: str, max_results: int) -> bytes:
    params = urllib.parse.urlencode({
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    })
    for attempt in (1, 2):
        arxiv_throttle()
        try:
            return http_get(f"{API_URL}?{params}", TIMEOUT_S)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503) and attempt == 1:
                logger.warning("arXiv returned %s, retrying once in 10 s", exc.code)
                time.sleep(10)
                continue
            raise RuntimeError(f"arXiv API error {exc.code} for query {search_query!r}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == 1:
                logger.warning("arXiv unreachable (%s), retrying once", exc)
                continue
            raise RuntimeError(f"arXiv API unreachable: {exc}") from exc
    raise AssertionError("unreachable")


def search_arxiv(query: str, max_results: int = 15) -> list[dict]:
    """Search arXiv and return paper metadata, most relevant first.

    Args:
        query: Free-text keywords, e.g. "contrastive learning image representation".
            Every word must match. Advanced arXiv syntax is also accepted, e.g.
            'ti:"contrastive learning" AND submittedDate:[202001010000 TO 202512312359]'.
        max_results: Number of papers to return (1 to 30, default 15).

    Returns:
        A list of dicts with keys: arxiv_id, title, authors (list of names),
        year (int), abstract, pdf_url. Empty list if nothing matches.
    """
    query = " ".join(query.split())
    if not query:
        raise ValueError("query must not be empty")
    max_results = max(1, min(int(max_results), MAX_RESULTS_CAP))
    search_query = _build_search_query(query)

    key = hashlib.sha1(f"{search_query}|{max_results}".encode("utf-8")).hexdigest()
    cache_file = ARXIV_CACHE_DIR / f"{key}.json"
    if cache_file.is_file():
        logger.info("arXiv cache hit for %r", query)
        return json.loads(cache_file.read_text(encoding="utf-8"))["papers"]

    logger.info("arXiv request: %s (max %d)", search_query, max_results)
    papers = _parse_feed(_fetch(search_query, max_results))

    # Empty answers are not cached: arXiv sometimes returns an empty feed transiently.
    if papers:
        ARXIV_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(
            json.dumps(
                {"query": query, "search_query": search_query, "max_results": max_results, "papers": papers},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    return papers
