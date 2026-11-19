"""
chunker.py -- Semantic Text Chunking Module
=============================================
Splits extracted text into meaningful chunks for retrieval.

Three strategies:
  1. SEMANTIC (best quality):
     Groups sentences by topic similarity using embeddings.
     Adjacent sentences with cosine similarity > 0.6 stay together.

  2. PARAGRAPH:
     Splits on double newlines (natural paragraph breaks).
     Merges short paragraphs, splits long ones at sentence boundaries.

  3. FIXED (fallback):
     150-word sliding window with 30-word overlap.
     Always splits at sentence boundaries -- never mid-sentence.

Auto-selection logic:
  - Under 100 words: single chunk, skip chunking
  - Many paragraph breaks (>5 double newlines): paragraph strategy
  - Over 500 words with few breaks: semantic strategy
  - Under 500 words: fixed strategy

Post-processing:
  - Removes chunks under 25 words
  - Removes near-duplicate chunks (Jaccard similarity > 0.85)
  - Assigns chunk_id to each chunk for tracking

Usage:
  python -m core.chunker --file "paper.pdf" --strategy auto

Dependencies:
  pip install spacy sentence-transformers scikit-learn
  python -m spacy download en_core_web_sm
"""

import argparse
import os
import sys
import re

# Lazy-loaded globals to avoid slow imports at module level
_nlp = None
_embedder = None


def _get_nlp():
    """
    Lazy-load spaCy model. Only loads once, reuses on subsequent calls.
    spaCy takes ~1s to load so we avoid paying that cost at import time.
    """
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("en_core_web_sm")
            print("    [spaCy model loaded]")
        except OSError:
            raise ImportError(
                "spaCy model not found. Run: python -m spacy download en_core_web_sm"
            )
    return _nlp


def _get_embedder():
    """
    Lazy-load sentence-transformers model for semantic similarity.
    Using all-MiniLM-L6-v2: small (80MB), fast, good for English.
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


def _split_sentences(text: str) -> list:
    """
    Split text into sentences using spaCy.

    Why spaCy instead of regex?
      Handles abbreviations (Dr., U.S.A.), decimal numbers (3.14),
      quotes, and nested punctuation much more accurately.
    """
    nlp = _get_nlp()

    max_length = nlp.max_length
    if len(text) > max_length:
        sentences = []
        for i in range(0, len(text), max_length - 500):
            segment = text[i:i + max_length]
            doc = nlp(segment)
            for sent in doc.sents:
                sent_text = sent.text.strip()
                if sent_text and len(sent_text) > 5:
                    sentences.append(sent_text)
        return sentences

    doc = nlp(text)
    return [
        sent.text.strip()
        for sent in doc.sents
        if sent.text.strip() and len(sent.text.strip()) > 5
    ]


# =====================================================================
# STRATEGY 1: Semantic Chunking
# =====================================================================
def _chunk_semantic(sentences: list) -> list:
    """
    Group sentences by topic similarity using embeddings.

    Algorithm:
      1. Encode each sentence into a 384-dim vector
      2. Compare adjacent sentences via cosine similarity
      3. If sim > 0.6: same chunk (same topic continues)
      4. If sim < 0.6: new chunk (topic changed)
      5. Min 3, max 10 sentences per chunk

    Threshold 0.6 was chosen empirically:
      - 0.8+ makes chunks too small (every sentence alone)
      - 0.3 makes chunks too large (mixing topics)
      - 0.6 captures natural topic shifts well
    """
    if len(sentences) <= 3:
        return [" ".join(sentences)]

    embedder = _get_embedder()

    print("    Computing sentence embeddings...")
    embeddings = embedder.encode(sentences, show_progress_bar=False)

    from sklearn.metrics.pairwise import cosine_similarity
    chunks = []
    current_chunk = [sentences[0]]

    for i in range(1, len(sentences)):
        sim = cosine_similarity(
            [embeddings[i - 1]], [embeddings[i]]
        )[0][0]

        if sim >= 0.6 and len(current_chunk) < 10:
            current_chunk.append(sentences[i])
        else:
            if len(current_chunk) >= 3:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentences[i]]
            else:
                # Chunk too small -- keep adding until we hit 3
                current_chunk.append(sentences[i])
                if len(current_chunk) >= 3 and i + 1 < len(sentences):
                    next_sim = cosine_similarity(
                        [embeddings[i]], [embeddings[i + 1]]
                    )[0][0]
                    if next_sim < 0.6:
                        chunks.append(" ".join(current_chunk))
                        current_chunk = []

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


# =====================================================================
# STRATEGY 2: Paragraph Chunking
# =====================================================================
def _chunk_paragraph(text: str) -> list:
    """
    Split on paragraph boundaries (double newlines).
    Merges short paragraphs (<50 words), splits long ones (>200 words).
    """
    paragraphs = re.split(r"\n\s*\n", text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    # Merge short paragraphs
    merged = []
    buffer = ""
    for para in paragraphs:
        if buffer:
            buffer = buffer + " " + para
        else:
            buffer = para

        if len(buffer.split()) >= 50:
            merged.append(buffer)
            buffer = ""

    if buffer:
        if merged:
            merged[-1] = merged[-1] + " " + buffer
        else:
            merged.append(buffer)

    # Split long paragraphs at sentence boundaries
    chunks = []
    for para in merged:
        word_count = len(para.split())
        if word_count > 200:
            sents = _split_sentences(para)
            current = []
            current_words = 0
            for sent in sents:
                sent_words = len(sent.split())
                if current_words + sent_words > 200 and current:
                    chunks.append(" ".join(current))
                    current = [sent]
                    current_words = sent_words
                else:
                    current.append(sent)
                    current_words += sent_words
            if current:
                chunks.append(" ".join(current))
        else:
            chunks.append(para)

    return chunks


# =====================================================================
# STRATEGY 3: Fixed-Size Chunking
# =====================================================================
def _chunk_fixed(sentences: list, window_words: int = 150,
                 overlap_words: int = 30) -> list:
    """
    Fixed-size word windows with overlap.
    Always splits at sentence boundaries -- never mid-sentence.
    """
    chunks = []
    current_chunk = []
    current_words = 0

    for sent in sentences:
        sent_words = len(sent.split())
        current_chunk.append(sent)
        current_words += sent_words

        if current_words >= window_words:
            chunks.append(" ".join(current_chunk))

            # Keep last few sentences as overlap for context continuity
            overlap_chunk = []
            overlap_count = 0
            for s in reversed(current_chunk):
                s_words = len(s.split())
                if overlap_count + s_words <= overlap_words:
                    overlap_chunk.insert(0, s)
                    overlap_count += s_words
                else:
                    break

            current_chunk = overlap_chunk
            current_words = overlap_count

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


# =====================================================================
# Post-processing
# =====================================================================
def _postprocess_chunks(chunks: list) -> list:
    """
    Clean up chunks:
      1. Remove chunks under 25 words (too small for retrieval)
      2. Remove near-duplicates (Jaccard word overlap > 0.85)
    """
    # Keep short chunks if they hold facts (numbers / KEY: value).
    # A 12-word "ACCOUNT NUMBER: PK89..." line is more useful than a
    # 40-word filler paragraph.
    filtered = []
    for c in chunks:
        words = len(c.split())
        is_fact = bool(re.search(r"\d|[A-Z][A-Z0-9 _]{1,40}:", c))
        if words >= 15 or is_fact:
            filtered.append(c)
    if not filtered:
        return chunks  # Keep originals if all too small

    # Remove near-duplicates using Jaccard similarity
    deduplicated = [filtered[0]]
    for i in range(1, len(filtered)):
        is_dup = False
        words_i = set(filtered[i].lower().split())

        for existing in deduplicated:
            words_e = set(existing.lower().split())
            if not words_i or not words_e:
                continue
            intersection = words_i & words_e
            union = words_i | words_e
            jaccard = len(intersection) / len(union)

            if jaccard > 0.85:
                is_dup = True
                break

        if not is_dup:
            deduplicated.append(filtered[i])

    return deduplicated


# =====================================================================
# Auto-select strategy
# =====================================================================
def _auto_select_strategy(text: str) -> str:
    """
    Pick the best strategy for the text.
      - Under 100 words: single chunk
      - 5+ paragraph breaks: paragraph strategy
      - Over 500 words: semantic strategy
      - Under 500 words: fixed strategy
    """
    word_count = len(text.split())

    if word_count < 100:
        return "single"

    paragraph_breaks = len(re.findall(r"\n\s*\n", text))

    if paragraph_breaks > 5:
        return "paragraph"
    elif word_count > 500:
        return "semantic"
    else:
        return "fixed"


# =====================================================================
# Exact String Deduplication
# =====================================================================
def _deduplicate_exact(chunks: list) -> list:
    """
    Remove exact duplicate chunks (after normalizing whitespace + case).
    More aggressive than Jaccard -- catches chunks that are identical
    but have different spacing.
    """
    seen = set()
    unique = []
    for chunk in chunks:
        normalized = re.sub(r'\s+', ' ', chunk.strip().lower())
        if normalized not in seen and len(normalized) > 10:
            seen.add(normalized)
            unique.append(chunk)
    return unique


# =====================================================================
# Filter citation noise from chunks
# =====================================================================
def _filter_citation_noise(chunks: list) -> list:
    """
    Clean citation artifacts from each chunk and remove chunks
    that are mostly bibliography/reference noise.

    Removes:
      - Inline citations: (Author et al., 2023), (Smith, 2020)
      - DOI patterns: 10.18653/v1/D18-1259
      - Spaced DOI artifacts: 18653 / v1 / D18 - 1259
      - Chunks that are mostly names/citations (< 20 real content words)
    """
    cleaned = []
    for chunk in chunks:
        # Remove inline citations like (Author et al., 2023)
        chunk = re.sub(r'\([A-Z][a-z]+ et al\.,?\s*\d{4}[a-z]?\)', '', chunk)
        chunk = re.sub(r'\([A-Z][a-z]+,?\s*\d{4}[a-z]?\)', '', chunk)
        # Remove multi-author citations: (Author1 and Author2, 2023)
        chunk = re.sub(r'\([A-Z][a-z]+ and [A-Z][a-z]+,?\s*\d{4}[a-z]?\)', '', chunk)

        # Remove DOI patterns
        chunk = re.sub(r'\d+\.\d+/[^\s]+', '', chunk)
        chunk = re.sub(r'\d{4,}\s*/\s*v\d+\s*/\s*[A-Z]\d+\s*-?\s*\d+', '', chunk)

        # Remove arXiv IDs
        chunk = re.sub(r'arXiv:\d+\.\d+', '', chunk)

        # Clean up multiple spaces left by removals
        chunk = re.sub(r'\s{2,}', ' ', chunk).strip()

        # Skip chunks that are too short after cleaning, unless they
        # still hold a number or structured field.
        word_count = len(chunk.split())
        is_fact = bool(re.search(r"\d|[A-Z][A-Z0-9 _]{1,40}:", chunk))
        if word_count < 15 and not is_fact:
            continue

        # Skip chunks that look like bibliography entries
        # (high ratio of capitalized words = author names)
        words = chunk.split()
        cap_words = sum(1 for w in words if w and w[0].isupper() and len(w) > 1)
        cap_ratio = cap_words / max(len(words), 1)
        # If >60% capitalized and short, likely a reference entry
        if cap_ratio > 0.6 and word_count < 50:
            continue

        cleaned.append(chunk)

    return cleaned


# =====================================================================
# Record Block Extraction (for structured documents like bank reports)
# =====================================================================
def _extract_record_blocks(text: str) -> tuple:
    """
    Detect structured record blocks and keep them intact as chunks.

    Uses PRECISE field-by-field regex to extract complete records:
      RECORD_ID -> ACCOUNT HOLDER -> CITY -> ACCOUNT NUMBER ->
      BRANCH CODE -> STATUS -> CLEARING ZONE

    Deduplicates by RECORD_ID so each unique record appears once.

    Returns:
        (record_chunks, remaining_text)
        record_chunks: list of clean, formatted record strings
        remaining_text: text with record blocks removed
    """
    # Precise field-by-field pattern matching each line
    record_pattern = re.compile(
        r'RECORD_ID:\s*(.+?)\s*\n'
        r'ACCOUNT\s*HOLDER:\s*(.+?)\s*\n'
        r'CITY:\s*(.+?)\s*\n'
        r'ACCOUNT\s*NUMBER:\s*(.+?)\s*\n'
        r'BRANCH\s*CODE:\s*(.+?)\s*\n'
        r'STATUS:\s*(.+?)\s*\n'
        r'CLEARING\s*ZONE:\s*(.+?)(?:\s*\n|$)',
        re.IGNORECASE
    )

    matches = list(record_pattern.finditer(text))

    if not matches:
        return [], text

    # Deduplicate by RECORD_ID (same record may appear on multiple pages)
    seen_ids = set()
    record_chunks = []
    positions = []

    for match in matches:
        record_id = match.group(1).strip()

        if record_id in seen_ids:
            # Still remove from text, but don't add as chunk
            positions.append((match.start(), match.end()))
            continue

        seen_ids.add(record_id)

        # Build a clean, formatted record block
        block = (
            f"RECORD_ID: {record_id}\n"
            f"ACCOUNT HOLDER: {match.group(2).strip()}\n"
            f"CITY: {match.group(3).strip()}\n"
            f"ACCOUNT NUMBER: {match.group(4).strip()}\n"
            f"BRANCH CODE: {match.group(5).strip()}\n"
            f"STATUS: {match.group(6).strip()}\n"
            f"CLEARING ZONE: {match.group(7).strip()}"
        )
        record_chunks.append(block)
        positions.append((match.start(), match.end()))

    # Remove ALL record blocks from text (including duplicates)
    remaining = text
    for start, end in sorted(positions, reverse=True):
        remaining = remaining[:start] + remaining[end:]

    # Clean up empty lines left behind
    remaining = re.sub(r'\n{3,}', '\n\n', remaining)

    if record_chunks:
        print(f"  Record blocks found: {len(record_chunks)} unique "
              f"(from {len(matches)} total, {len(matches) - len(record_chunks)} duplicates removed)")

    return record_chunks, remaining


# =====================================================================
# Main chunking function -- the public API
# =====================================================================
def chunk_text(text: str, strategy: str = "auto") -> dict:
    """
    Split text into meaningful chunks for retrieval.

    This is the MAIN function -- call this from the pipeline.

    Args:
        text: The full extracted text to chunk.
        strategy: "auto", "semantic", "paragraph", or "fixed"

    Returns:
        dict with keys:
            - chunks: list[str]
            - chunk_ids: list[int]
            - count: int
            - strategy_used: str
            - avg_chunk_words: float
            - total_words: int
    """
    print(f"\n{'=' * 60}")
    print(f"  TEXT CHUNKING")
    print(f"{'=' * 60}")

    total_words = len(text.split())
    print(f"  Input words: {total_words:,}")

    # Step 0: Extract record blocks FIRST -- keep them intact
    record_chunks, remaining_text = _extract_record_blocks(text)

    # Auto-select strategy (based on remaining text)
    working_text = remaining_text if record_chunks else text
    if strategy == "auto":
        strategy = _auto_select_strategy(working_text)
        print(f"  Auto-selected: {strategy}")
    else:
        print(f"  Strategy: {strategy}")

    # Single chunk for very short text
    remaining_words = len(working_text.split())
    if strategy == "single" or remaining_words < 100:
        if record_chunks:
            # Still have record blocks
            chunks = record_chunks + ([working_text.strip()] if working_text.strip() else [])
        else:
            print(f"  Text too short for chunking -- single chunk")
            chunks = [text.strip()]
        chunks = _deduplicate_exact(chunks)
        return {
            "chunks": chunks,
            "chunk_ids": list(range(len(chunks))),
            "count": len(chunks),
            "strategy_used": "single",
            "avg_chunk_words": total_words // max(len(chunks), 1),
            "total_words": total_words,
        }

    # Split into sentences for semantic and fixed strategies
    if strategy in ("semantic", "fixed"):
        print(f"  Splitting into sentences...")
        sentences = _split_sentences(working_text)
        print(f"  Sentences found: {len(sentences)}")

    # Apply strategy on remaining text (without record blocks)
    if strategy == "semantic":
        print(f"  Running semantic chunking...")
        chunks = _chunk_semantic(sentences)
    elif strategy == "paragraph":
        print(f"  Running paragraph chunking...")
        chunks = _chunk_paragraph(working_text)
    elif strategy == "fixed":
        print(f"  Running fixed-size chunking...")
        chunks = _chunk_fixed(sentences)
    else:
        raise ValueError(f"Unknown strategy: '{strategy}'. "
                         f"Use: auto, semantic, paragraph, or fixed")

    # Post-process: remove tiny/duplicate chunks
    original_count = len(chunks)
    chunks = _postprocess_chunks(chunks)

    # Filter citation noise from each chunk
    chunks = _filter_citation_noise(chunks)

    # Combine: record blocks FIRST (high priority), then normal chunks
    if record_chunks:
        chunks = record_chunks + chunks
        print(f"  Combined: {len(record_chunks)} record blocks + {len(chunks) - len(record_chunks)} normal chunks")

    # Exact string deduplication
    chunks = _deduplicate_exact(chunks)

    removed = original_count + len(record_chunks) - len(chunks)
    if removed > 0:
        print(f"  Post-processing: removed {removed} tiny/duplicate/noisy chunks")

    # Assign chunk IDs
    chunk_ids = list(range(len(chunks)))

    # Stats
    chunk_word_counts = [len(c.split()) for c in chunks]
    avg_words = round(sum(chunk_word_counts) / max(len(chunks), 1), 1)

    result = {
        "chunks": chunks,
        "chunk_ids": chunk_ids,
        "count": len(chunks),
        "strategy_used": strategy,
        "avg_chunk_words": avg_words,
        "total_words": total_words,
    }

    # Print summary
    print(f"\n  --- Chunking Summary ---")
    print(f"  Strategy:      {strategy}")
    print(f"  Chunks:        {len(chunks)}")
    print(f"  Avg words:     {avg_words}")
    print(f"  Min words:     {min(chunk_word_counts) if chunk_word_counts else 0}")
    print(f"  Max words:     {max(chunk_word_counts) if chunk_word_counts else 0}")
    print(f"  Total words:   {total_words:,}")

    # Preview first 3 chunks
    print(f"\n  --- Chunk Previews ---")
    for i, chunk in enumerate(chunks[:3]):
        preview = chunk[:120] + "..." if len(chunk) > 120 else chunk
        words = len(chunk.split())
        print(f"  [{i}] ({words} words): {preview}")
    if len(chunks) > 3:
        print(f"  ... and {len(chunks) - 3} more chunks")

    print(f"{'=' * 60}\n")

    return result


# -- CLI entry point ---------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="COF-RAG Text Chunker -- splits text into meaningful chunks"
    )
    parser.add_argument(
        "--file", required=True,
        help="Path to a text file or PDF to chunk"
    )
    parser.add_argument(
        "--strategy", default="auto",
        choices=["auto", "semantic", "paragraph", "fixed"],
        help="Chunking strategy (default: auto)"
    )
    args = parser.parse_args()

    # Extract text first if PDF
    if args.file.lower().endswith(".pdf"):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from core.extractor import extract_text
        extraction = extract_text(args.file, "digital_pdf")
        text = extraction["text"]
    else:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()

    try:
        result = chunk_text(text, args.strategy)
        print(f"\nTotal chunks: {result['count']} | IDs: {result['chunk_ids'][:5]}...")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
