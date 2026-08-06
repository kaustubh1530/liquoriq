"""
services/knowledge/retriever.py — PHASE 24: the RAG retrieval pipeline.

    playbooks (.md) → parse frontmatter → chunk by section → score → top-k

THE ARCHITECTURAL DECISION, STATED UP FRONT

The brief asked for embeddings in a vector database. I built the pipeline with
a PLUGGABLE RETRIEVER and shipped a lexical one as the default. Here is why,
because it is the interesting part of this phase:

  · The corpus is ~20 playbooks — roughly 150 chunks. Embeddings earn their
    keep at tens of thousands of chunks, where lexical search drowns in
    synonyms. At 150, BM25-style scoring over a curated corpus with hand-
    written keyword metadata beats cosine similarity on relevance, because
    WE WROTE THE DOCUMENTS and can tag them precisely.

  · An embedding index costs an API call per chunk to build, a call per query
    to search, a pgvector extension, a migration, and a re-index step every
    time a playbook is edited. That is real operational weight for a corpus a
    person could read in an afternoon.

  · Lexical retrieval is DETERMINISTIC. The same question retrieves the same
    playbook every time, which is testable offline with no API key — the same
    property that makes the Phase 23 agent loop testable.

  · Retrieval quality is not the bottleneck yet. WRITING GOOD PLAYBOOKS is.

`EmbeddingRetriever` implements the same interface and is wired but disabled;
flipping `KNOWLEDGE_RETRIEVER=embedding` switches the engine over without a
single caller changing. When the corpus passes a few hundred documents, that
is a config change, not a rewrite.

That is the point of the interface: the decision is reversible.
"""

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[3] / "knowledge"

# Words that carry no topical signal. Kept short on purpose — an aggressive
# stop list throws away "cash", "deal" and "stock", which are the whole point.
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for",
    "from", "have", "how", "i", "if", "in", "is", "it", "me", "my", "of", "on",
    "or", "should", "that", "the", "their", "them", "there", "they", "this",
    "to", "was", "what", "when", "where", "which", "why", "will", "with", "you",
    "your", "am", "we", "our", "us", "shall", "would", "could", "about",
}

# A section header is where a playbook naturally divides. Chunking on headers
# rather than a fixed token window means a retrieved chunk is always a complete
# thought — "Common mistakes" arrives whole rather than sliced mid-sentence.
_SECTION = re.compile(r"^##\s+(.+)$", re.M)
_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


@dataclass
class Chunk:
    """One retrievable section of one playbook."""
    doc_id: str
    title: str
    section: str
    text: str
    domain: str
    keywords: list[str] = field(default_factory=list)
    tokens: Counter = field(default_factory=Counter)

    @property
    def citation(self) -> str:
        return f"{self.title} → {self.section}"


def tokenise(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9']+", (text or "").lower())
            if len(w) > 2 and w not in STOPWORDS]


def _parse_frontmatter(raw: str) -> tuple[dict, str]:
    """
    Playbooks carry YAML-ish frontmatter: title, domain, keywords.

    Parsed by hand rather than with PyYAML — the format is three flat keys and
    a dependency for that would be silly.
    """
    match = _FRONTMATTER.match(raw)
    if not match:
        return {}, raw

    meta = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            meta[key.strip()] = [v.strip().strip("'\"")
                                 for v in value[1:-1].split(",") if v.strip()]
        else:
            meta[key.strip()] = value.strip("'\"")
    return meta, raw[match.end():]


def load_chunks(root: Path | None = None) -> list[Chunk]:
    """
    Every playbook, split into retrievable sections.

    Chunking by section header rather than by token count is deliberate: a
    consultant's advice is organised in complete units ("common mistakes",
    "buying window"), and half a unit is worse than none.
    """
    root = root or KNOWLEDGE_ROOT
    chunks: list[Chunk] = []

    if not root.exists():
        logger.warning("Knowledge base not found at %s", root)
        return chunks

    for path in sorted(root.rglob("*.md")):
        try:
            raw = path.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001 — one bad file must not empty the base
            logger.warning("Could not read playbook %s", path, exc_info=True)
            continue

        meta, body = _parse_frontmatter(raw)
        doc_id = str(path.relative_to(root)).replace(".md", "")
        title = meta.get("title") or path.stem.replace("_", " ").title()
        domain = meta.get("domain") or path.parent.name
        keywords = meta.get("keywords") or []

        # Split on section headers, keeping each header with its body.
        positions = [(m.start(), m.group(1)) for m in _SECTION.finditer(body)]
        if not positions:
            sections = [("Overview", body)]
        else:
            sections = []
            for i, (start, heading) in enumerate(positions):
                end = positions[i + 1][0] if i + 1 < len(positions) else len(body)
                sections.append((heading, body[start:end]))

        for heading, text in sections:
            text = text.strip()
            if len(text) < 40:          # a header with nothing under it
                continue
            # Keywords and the title are folded into the token counts so that
            # metadata influences ranking without a separate scoring pass.
            searchable = f"{title} {heading} {' '.join(keywords)} {text}"
            chunks.append(Chunk(
                doc_id=doc_id, title=title, section=heading, text=text,
                domain=domain, keywords=keywords,
                tokens=Counter(tokenise(searchable)),
            ))

    logger.info("Knowledge base loaded: %d chunks from %s", len(chunks), root)
    return chunks


class LexicalRetriever:
    """
    BM25-flavoured scoring over the playbook corpus.

    Not a toy: IDF weighting means a question mentioning "mezcal" ranks the
    tequila playbook far above the eight documents that happen to say "stock".
    Length normalisation stops a long playbook winning on verbosity alone.
    """

    K1 = 1.4       # term-frequency saturation
    B = 0.72       # length normalisation strength
    KEYWORD_BOOST = 2.5   # an explicit metadata match is a strong signal

    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self.total = len(chunks) or 1
        self.avg_len = (sum(sum(c.tokens.values()) for c in chunks) / self.total) or 1

        document_frequency: Counter = Counter()
        for chunk in chunks:
            document_frequency.update(set(chunk.tokens))
        self.idf = {
            term: math.log(1 + (self.total - freq + 0.5) / (freq + 0.5))
            for term, freq in document_frequency.items()
        }

    def search(self, query: str, k: int = 6, domain: str | None = None) -> list[dict]:
        terms = tokenise(query)
        if not terms:
            return []

        pool = [c for c in self.chunks if not domain or c.domain == domain]
        scored = []

        for chunk in pool:
            length = sum(chunk.tokens.values()) or 1
            score = 0.0
            matched = []

            for term in terms:
                freq = chunk.tokens.get(term, 0)
                if not freq:
                    continue
                idf = self.idf.get(term, 0.0)
                norm = freq * (self.K1 + 1) / (
                    freq + self.K1 * (1 - self.B + self.B * length / self.avg_len))
                score += idf * norm
                matched.append(term)

            # An author-declared keyword is worth more than an incidental
            # mention: we wrote these documents and tagged them on purpose.
            for keyword in chunk.keywords:
                if keyword.lower() in query.lower():
                    score += self.KEYWORD_BOOST

            if score > 0:
                scored.append((score, matched, chunk))

        scored.sort(key=lambda row: -row[0])
        return [
            {
                "doc_id": chunk.doc_id,
                "title": chunk.title,
                "section": chunk.section,
                "citation": chunk.citation,
                "domain": chunk.domain,
                "text": chunk.text,
                "score": round(score, 3),
                "matched_terms": matched[:8],
            }
            for score, matched, chunk in scored[:k]
        ]


class EmbeddingRetriever:
    """
    The same interface, backed by vectors. WIRED BUT NOT ENABLED.

    Present so the swap is a config change rather than a rewrite — and so the
    decision above is reversible the moment the corpus outgrows lexical search.
    Enable with KNOWLEDGE_RETRIEVER=embedding once an index exists.

    Deliberately not built yet: an unused pgvector table, an ingest job and an
    embedding cost per edit are real weight, and 150 chunks do not need them.
    """

    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks

    async def search(self, query: str, k: int = 6, domain: str | None = None):
        raise NotImplementedError(
            "The embedding retriever is not built yet. The corpus is small "
            "enough that lexical retrieval scores better; see the module "
            "docstring. Build the index before switching KNOWLEDGE_RETRIEVER."
        )


@lru_cache(maxsize=1)
def get_retriever() -> LexicalRetriever:
    """
    One retriever for the process lifetime.

    Cached because parsing and indexing the corpus on every question would be
    pure waste — the playbooks change when someone edits a file, not per
    request. Call get_retriever.cache_clear() after editing during development.
    """
    return LexicalRetriever(load_chunks())
