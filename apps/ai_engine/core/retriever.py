"""
retriever.py -- Hybrid Relevance Retrieval Module
===================================================
Finds the most relevant chunks for a query using TWO methods combined:

  METHOD 1 -- Dense semantic (weight 0.6):
    sentence-transformers/all-MiniLM-L6-v2 encodes chunks + query
    into vectors, then cosine similarity finds meaning-based matches.
    "car" matches "automobile" even without keyword overlap.

  METHOD 2 -- BM25 sparse keyword (weight 0.4):
    BM25Okapi scores chunks by exact term frequency, IDF weighting,
    and document length normalization. Catches exact terms that
    semantic models sometimes miss (names, model numbers, etc.).

  Final score = (dense * 0.6) + (bm25_normalized * 0.4)

Why hybrid?
  Dense alone misses exact keywords. BM25 alone misses paraphrases.
  Combining both gives the best of both worlds -- confirmed by
  research (e.g., ColBERT, Hybrid Dense Retrieval papers).

Usage:
  python -m core.retriever --file "paper.pdf" --query "your question"

Dependencies:
  pip install sentence-transformers rank-bm25 scikit-learn numpy
"""

import argparse
import os
import sys
import numpy as np

# Lazy-loaded embedder
_embedder = None


def _get_embedder():
    """
    Lazy-load sentence-transformers model.
    all-MiniLM-L6-v2: 80MB, fast, good for English retrieval.
    """
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer("all-MiniLM-L6-v2")
            print("    [Embedding model loaded]")
        except Exception as e:
            raise ImportError(f"sentence-transformers error: {e}")
    return _embedder


def _dense_retrieval(chunks: list, query: str) -> np.ndarray:
    """
    Compute semantic similarity between query and each chunk.
    Returns array of cosine similarity scores (roughly -1.0 to 1.0).
    """
    from sklearn.metrics.pairwise import cosine_similarity

    embedder = _get_embedder()

    all_texts = chunks + [query]
    embeddings = embedder.encode(all_texts, show_progress_bar=False)

    query_embedding = embeddings[-1].reshape(1, -1)
    chunk_embeddings = embeddings[:-1]

    similarities = cosine_similarity(query_embedding, chunk_embeddings)[0]
    return similarities


def _sparse_retrieval(chunks: list, query: str) -> np.ndarray:
    """
    Compute BM25 keyword-based scores between query and each chunk.
    Returns array of normalized scores (0.0 to 1.0).

    BM25 scores based on: term frequency, inverse document frequency,
    and document length normalization.
    """
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        raise ImportError("rank-bm25 not installed. Run: pip install rank-bm25")

    tokenized_chunks = [chunk.lower().split() for chunk in chunks]
    tokenized_query = query.lower().split()

    bm25 = BM25Okapi(tokenized_chunks)
    scores = bm25.get_scores(tokenized_query)

    # Normalize to 0-1
    max_score = scores.max() if scores.max() > 0 else 1.0
    return scores / max_score


def retrieve_relevant(chunks: list, query: str, top_k: int = 5,
                      chunk_ids: list = None, target_words: int = 1200) -> dict:
    """
    Find the most relevant chunks using hybrid retrieval.

    This is the MAIN function -- call this from the pipeline.

    Args:
        chunks: List of text chunks to search.
        query: The user's question.
        top_k: Minimum number of top chunks to return (default 5).
        chunk_ids: Optional list of chunk IDs matching chunks.
                   If None, uses sequential indices.
        target_words: Desired size of the FINAL context. More chunks are
                      retrieved for larger targets (default 1200 = ~2-3 pages).

    Returns:
        dict with keys:
            - relevant_chunks: list[str]
            - chunk_ids: list[int]
            - scores: list[float]
            - dense_scores: list[float]
            - bm25_scores: list[float]
            - retrieval_method: str
    """
    print(f"\n{'=' * 60}")
    print(f"  RELEVANCE RETRIEVAL")
    print(f"{'=' * 60}")
    print(f"  Query: {query}")
    print(f"  Searching {len(chunks)} chunks...")
    print(f"  Method: Hybrid (Dense 60% + BM25 40%)")

    if chunk_ids is None:
        chunk_ids = list(range(len(chunks)))

    if len(chunks) == 0:
        print("  [WARNING] No chunks to search!")
        return {
            "relevant_chunks": [],
            "chunk_ids": [],
            "scores": [],
            "dense_scores": [],
            "bm25_scores": [],
            "retrieval_method": "hybrid",
        }

    # Budget-based top_k: fetch enough text that compression still has
    # complete details to work with. WHY x2.8: Stage 1 used to drop ~40%
    # of sentences AND the 0.1 score floor used to keep only 2 chunks on
    # generic queries ("summarize", "complete details"). Over-fetching
    # is cheaper than missing answers.
    avg_chunk_words = max(1.0, sum(len(c.split()) for c in chunks) / len(chunks))
    budget_k = int((target_words * 2.8) / avg_chunk_words) + 1
    budget_k = max(8, min(80, budget_k))
    if budget_k > top_k:
        print(f"  [Budget] target {target_words} words, avg chunk "
              f"{avg_chunk_words:.0f} words -> top_k={budget_k}")
        top_k = budget_k

    top_k = min(top_k, len(chunks))

    # -- Step 1: Dense retrieval ------------------------------------
    print(f"\n  Step 1: Dense retrieval (semantic)...")
    try:
        dense_scores = _dense_retrieval(chunks, query)
        print(f"    Range: {dense_scores.min():.3f} to {dense_scores.max():.3f}")
    except Exception as e:
        print(f"    [WARNING] Dense failed: {e} -- using BM25 only")
        dense_scores = np.zeros(len(chunks))

    # -- Step 2: Sparse retrieval -----------------------------------
    print(f"  Step 2: Sparse retrieval (BM25)...")
    try:
        bm25_scores = _sparse_retrieval(chunks, query)
        print(f"    Range: {bm25_scores.min():.3f} to {bm25_scores.max():.3f}")
    except Exception as e:
        print(f"    [WARNING] BM25 failed: {e} -- using dense only")
        bm25_scores = np.zeros(len(chunks))

    # -- Step 3: Combine scores -------------------------------------
    DENSE_WEIGHT = 0.6
    BM25_WEIGHT = 0.4
    final_scores = (dense_scores * DENSE_WEIGHT) + (bm25_scores * BM25_WEIGHT)

    # -- Step 3b: Boost record blocks --------------------------------
    # Record blocks (from chunker) contain structured data like
    # account holders, IBANs, etc. Boost their scores by 1.5x.
    # WHY colon-suffixed labels: plain phrases like "account numbers"
    # also appear in filler sentences and must NOT be boosted.
    record_keywords = ['record_id:', 'account holder:', 'account number:',
                       'branch code:', 'clearing zone:']
    account_query_keywords = [
        'account', 'holder', 'name', 'city', 'iban', 'customer',
        'record', 'profile', 'branch', 'balance', 'number',
    ]
    query_lower = query.lower()
    force_include_records = any(kw in query_lower for kw in account_query_keywords)

    record_indices = []
    for i, chunk in enumerate(chunks):
        chunk_lower = chunk.lower()
        if any(kw in chunk_lower for kw in record_keywords):
            record_indices.append(i)
            final_scores[i] *= 1.5  # Boost record block score
            print(f"    [BOOST] Chunk {i} is a record block (score boosted 1.5x)")

    # -- Step 4: Select top_k ---------------------------------------
    # Relative cutoff: keep chunks that are close to the best match.
    # A hard 0.1 floor was dropping almost everything on broad queries
    # (scores of 0.04-0.09) and leaving only 2 chunks.
    sorted_indices = np.argsort(final_scores)[::-1]
    max_score = float(final_scores.max()) if len(final_scores) else 0.0
    relative_floor = max(0.02, max_score * 0.25)

    def _above_floor(idx):
        return float(final_scores[idx]) >= relative_floor or max_score < 0.05

    if force_include_records and record_indices:
        selected_indices = list(record_indices)
        print(f"  [FORCE-INCLUDE] {len(record_indices)} record blocks (query matches account keywords)")
    else:
        selected_indices = []

    for idx in sorted_indices:
        if idx in selected_indices:
            continue
        if _above_floor(idx) or len(selected_indices) < 4:
            selected_indices.append(int(idx))
        if len(selected_indices) >= top_k:
            break

    # Neighbor expansion: if chunk i is relevant, i-1 and i+1 usually
    # hold the rest of the same section (definitions, numbers, caveats).
    expanded = []
    seen = set()
    for idx in selected_indices:
        for neighbor in (idx - 1, idx, idx + 1):
            if 0 <= neighbor < len(chunks) and neighbor not in seen:
                seen.add(neighbor)
                expanded.append(neighbor)
    selected_indices = expanded[: min(len(chunks), max(top_k, len(expanded)))]
    print(f"  [Coverage] floor={relative_floor:.3f} (max={max_score:.3f}), "
          f"{len(selected_indices)} chunks after neighbor expansion")

    # Build results
    result = {
        "relevant_chunks": [chunks[i] for i in selected_indices],
        "chunk_ids": [chunk_ids[i] for i in selected_indices],
        "scores": [round(float(final_scores[i]), 4) for i in selected_indices],
        "dense_scores": [round(float(dense_scores[i]), 4) for i in selected_indices],
        "bm25_scores": [round(float(bm25_scores[i]), 4) for i in selected_indices],
        "retrieval_method": "hybrid",
    }

    # Print results
    print(f"\n  --- Retrieval Results (top {len(selected_indices)}) ---")
    for rank, idx in enumerate(selected_indices, 1):
        preview = chunks[idx][:100] + "..." if len(chunks[idx]) > 100 else chunks[idx]
        print(f"  #{rank} [score: {final_scores[idx]:.4f}] "
              f"(dense: {dense_scores[idx]:.3f}, bm25: {bm25_scores[idx]:.3f}) "
              f"chunk_id={chunk_ids[idx]}")
        print(f"      {preview}")

    print(f"\n  Selected: {len(selected_indices)} / {len(chunks)} chunks")
    print(f"  Best score: {result['scores'][0] if result['scores'] else 0}")
    print(f"{'=' * 60}\n")

    return result


# -- CLI entry point ---------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="COF-RAG Retriever -- finds relevant chunks for a query"
    )
    parser.add_argument("--file", required=True, help="Path to a PDF or text file")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--top_k", type=int, default=5, help="Top K chunks (default 5)")
    args = parser.parse_args()

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from core.extractor import extract_text
    from core.chunker import chunk_text

    if args.file.lower().endswith(".pdf"):
        extraction = extract_text(args.file, "digital_pdf")
    else:
        extraction = extract_text(args.file, "text_file")

    chunking = chunk_text(extraction["text"], strategy="semantic")

    try:
        result = retrieve_relevant(
            chunking["chunks"], args.query,
            top_k=args.top_k, chunk_ids=chunking["chunk_ids"]
        )
        print(f"\nRetrieved {len(result['relevant_chunks'])} chunks")
        print(f"Chunk IDs: {result['chunk_ids']}")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
