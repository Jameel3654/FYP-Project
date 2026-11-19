"""
compressor.py -- Two-Stage Context Compression Module
=======================================================
THIS IS THE CORE RESEARCH CONTRIBUTION OF COF-RAG.
No existing product does this exact two-stage pipeline.

STAGE 1 -- Sentence-level pruning with Cross-Encoder:
  Model: cross-encoder/ms-marco-MiniLM-L-6-v2
  Scores each sentence for relevance to the query.
  Irrelevant sentences are removed entirely.
  Fast coarse-grained first-pass reduction.

  NOTE: We originally planned to use Provence
  (naver/provence-reranker-debertav3-v1) but its custom architecture
  is incompatible with Python 3.14 + transformers 5.x.
  ms-marco-MiniLM is a proven cross-encoder reranker that works
  identically for sentence-level relevance scoring.

STAGE 2 -- Token-level compression with LLMLingua-2:
  Model: microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank
  Takes Stage 1 output and removes low-importance TOKENS.
  Fine-grained compression preserving key information.

FALLBACK -- if either model fails:
  Stage 1 fallback: skip pruning, keep all sentences
  Stage 2 fallback: TF-IDF extractive compression

Usage:
  python -m core.compressor --file "paper.pdf" --query "your question"

Dependencies:
  pip install sentence-transformers llmlingua spacy scikit-learn
"""

import argparse
import os
import re
import sys
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Lazy-loaded models
_cross_encoder = None
_cross_encoder_available = None
_llmlingua2_compressor = None
_llmlingua2_available = None
_nlp = None


def _get_nlp():
    """Lazy-load spaCy for sentence splitting."""
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("en_core_web_sm")
        except Exception:
            _nlp = None
    return _nlp


def _split_into_sentences(text: str) -> list:
    """Split text into sentences using spaCy, fallback to regex."""
    nlp = _get_nlp()
    if nlp is not None:
        try:
            doc = nlp(text[:nlp.max_length])
            sents = [s.text.strip() for s in doc.sents if s.text.strip()]
            if sents:
                return sents
        except Exception:
            pass
    sents = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sents if s.strip() and len(s.strip()) > 5]


# =====================================================================
# STAGE 1: Cross-Encoder Sentence-Level Pruning
# =====================================================================
def _check_cross_encoder():
    """Check if CrossEncoder can be loaded."""
    global _cross_encoder_available
    if _cross_encoder_available is None:
        try:
            from sentence_transformers import CrossEncoder
            _cross_encoder_available = True
        except ImportError:
            _cross_encoder_available = False
    return _cross_encoder_available


def _get_cross_encoder():
    """
    Lazy-load ms-marco cross-encoder for sentence relevance scoring.

    ms-marco-MiniLM-L-6-v2 is trained on MS MARCO passage ranking:
      - Standard architecture (works on all Python versions)
      - Small and fast (~90MB, CPU-friendly)
      - Highly accurate at judging query-passage relevance
      - Scores: higher = more relevant (typically -10 to +10 range)
    """
    global _cross_encoder
    if _cross_encoder is None:
        try:
            from sentence_transformers import CrossEncoder

            print("    Loading cross-encoder reranker...")
            _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            print("    [Cross-encoder ready]")
        except Exception as e:
            print(f"    [WARNING] Cross-encoder failed to load: {e}")
            _cross_encoder = None
    return _cross_encoder


_FACT_RE = re.compile(
    r"(?:\d|[$€£]|\b(?:19|20)\d{2}\b|(?i:pk)\d|[A-Z][A-Z0-9 _]{1,40}:)"
)


def _is_fact_sentence(sent: str) -> bool:
    """Sentences with numbers, keys, or money must never be pruned."""
    return bool(_FACT_RE.search(sent))


def _stage1_cross_encoder(sentences: list, query: str, target_words: int = 1200) -> dict:
    """
    Stage 1: Score each sentence with cross-encoder, keep relevant ones.

    The cross-encoder scores each (query, sentence) pair.
    Scores are typically in range -10 to +10.

    Completeness-first selection:
      1. Always keep fact sentences (numbers, KEY: value, years, money).
      2. Keep sentences whose score is near the best match (not only > 0).
         MS MARCO often scores useful supporting sentences negative.
      3. Fill remaining budget with next-best sentences so the output
         is a complete answer, not a 3-line summary.
      4. Output stays in ORIGINAL document order so it reads naturally.
    """
    encoder = _get_cross_encoder()
    if encoder is None:
        return None

    try:
        pairs = [[query, sent] for sent in sentences]
        scores = encoder.predict(pairs, show_progress_bar=False)

        ranked = sorted(range(len(sentences)), key=lambda i: scores[i], reverse=True)
        max_score = float(max(scores)) if len(scores) else 0.0
        # Relative bar: keep anything in the top band, even if < 0.
        relevant_bar = min(-1.5, max_score - 4.0) if max_score > 0 else -2.5

        selected = set()
        words = 0
        max_words = int(target_words * 1.6)

        # Pass 1: lock in fact sentences (IDs, amounts, dates, records)
        for i, sent in enumerate(sentences):
            if _is_fact_sentence(sent):
                selected.add(i)
                words += len(sent.split())

        # Pass 2: relevance + budget fill (best first)
        for i in ranked:
            if i in selected:
                continue
            sent_words = len(sentences[i].split())
            is_relevant = scores[i] >= relevant_bar
            under_budget = words < target_words
            room_for_relevant = is_relevant and words + sent_words <= max_words
            if under_budget or room_for_relevant:
                selected.add(i)
                words += sent_words
            elif scores[i] < relevant_bar - 2 and words >= int(target_words * 0.8):
                break

        # Never return a near-empty context
        for i in ranked[: max(8, min(12, len(ranked) // 3))]:
            if i not in selected:
                selected.add(i)

        kept_sentences = [sentences[i] for i in sorted(selected)]
        pruned_count = len(sentences) - len(kept_sentences)
        kept_text = " ".join(kept_sentences)

        return {
            "text": kept_text,
            "sentences_kept": len(kept_sentences),
            "sentences_pruned": pruned_count,
            "word_count": len(kept_text.split()),
        }

    except Exception as e:
        print(f"    [WARNING] Cross-encoder scoring failed: {e}")
        return None


# =====================================================================
# STAGE 2: LLMLingua-2 Token-Level Compression
# =====================================================================
def _check_llmlingua2():
    """Check if LLMLingua-2 can be loaded."""
    global _llmlingua2_available
    if _llmlingua2_available is None:
        try:
            import llmlingua
            _llmlingua2_available = True
        except ImportError:
            _llmlingua2_available = False
    return _llmlingua2_available


def _get_llmlingua2():
    """
    Lazy-load LLMLingua-2 compressor.

    Uses a BERT-based classifier trained on compression datasets to
    identify which tokens can be removed without losing meaning.
    Multilingual model supports future Urdu support.
    No API key needed -- runs entirely local on CPU.
    """
    global _llmlingua2_compressor
    if _llmlingua2_compressor is None:
        try:
            from llmlingua import PromptCompressor

            print("    Loading LLMLingua-2 compressor...")
            _llmlingua2_compressor = PromptCompressor(
                model_name="microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
                use_llmlingua2=True,
                device_map="cpu",
            )
            print("    [LLMLingua-2 ready]")
        except Exception as e:
            print(f"    [WARNING] LLMLingua-2 failed to load: {e}")
            _llmlingua2_compressor = None
    return _llmlingua2_compressor


def _stage2_llmlingua2(text: str, query: str, target_words: int = 1200) -> dict:
    """
    Stage 2: Token-level compression using LLMLingua-2.
    Removes individual low-importance tokens while preserving meaning.
    Compresses toward target_words (~1.35 BERT tokens per English word).
    """
    compressor = _get_llmlingua2()
    if compressor is None:
        return None

    try:
        segments = [seg.strip() for seg in text.split("\n\n") if seg.strip()]
        if not segments:
            segments = [text]

        # Gentle token trim only. 0.6 dynamic ratio was deleting names,
        # numbers and half-sentences. Keep ~85% of Stage 1 tokens.
        stage1_tokens = max(64, int(len(text.split()) * 1.35))
        target_token = max(
            int(target_words * 1.35),
            int(stage1_tokens * 0.85),
        )
        result = compressor.compress_prompt(
            segments,
            question=query,
            target_token=target_token,
            use_sentence_level_filter=False,
            context_budget="+200",
            dynamic_context_compression_ratio=0.0,
        )

        compressed = result.get("compressed_prompt", "")
        compressed = compressed.strip()
        compressed = re.sub(r"<\|endoftext\|>", "", compressed)
        compressed = re.sub(r"\s+", " ", compressed).strip()
        compressed = _fix_spacing_artifacts(compressed)

        if not compressed:
            return None

        return {
            "text": compressed,
            "word_count": len(compressed.split()),
        }

    except Exception as e:
        print(f"    [WARNING] LLMLingua-2 compression failed: {e}")
        return None


def _fix_spacing_artifacts(text: str) -> str:
    """
    Undo tokenizer spacing that LLMLingua-2 adds when it rebuilds text:
      "end - of - day"  -> "end-of-day"
      "( HSM )"         -> "(HSM)"
      "RECORD _ ID :"   -> "RECORD_ID:"
      "word ,"          -> "word,"
    WHY: these artifacts inflate word counts and look broken to users.
    """
    try:
        for _ in range(3):  # repeat for chains like "a - b - c"
            text = re.sub(r"(\w)\s+-\s+(\w)", r"\1-\2", text)
        text = re.sub(r"-{2,}", "-", text)
        text = re.sub(r"(\w)\s+_\s+(\w)", r"\1_\2", text)
        text = re.sub(r"(\w)\s+/\s+(\w)", r"\1/\2", text)
        text = re.sub(r"\(\s+", "(", text)
        text = re.sub(r"\s+\)", ")", text)
        text = re.sub(r"\s+([,.;:!?])", r"\1", text)
        return re.sub(r"\s{2,}", " ", text).strip()
    except Exception:
        return text


# =====================================================================
# FALLBACK: TF-IDF Extractive Compression
# =====================================================================
def _fallback_tfidf(text: str, query: str, target_words: int = 300) -> dict:
    """
    Fallback: score sentences by TF-IDF similarity to query,
    keep top ones in original order until target word count.
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        words = text.split()[:target_words]
        return {"text": " ".join(words), "word_count": len(words)}

    sentences = _split_into_sentences(text)
    if not sentences:
        words = text.split()[:target_words]
        return {"text": " ".join(words), "word_count": len(words)}

    all_texts = sentences + [query]
    vectorizer = TfidfVectorizer(stop_words="english")

    try:
        tfidf_matrix = vectorizer.fit_transform(all_texts)
    except ValueError:
        words = text.split()[:target_words]
        return {"text": " ".join(words), "word_count": len(words)}

    query_vec = tfidf_matrix[-1]
    sent_vecs = tfidf_matrix[:-1]
    scores = cosine_similarity(query_vec, sent_vecs)[0]

    scored = list(enumerate(zip(sentences, scores)))
    scored.sort(key=lambda x: x[1][1], reverse=True)

    selected = []
    total_words = 0
    for orig_idx, (sent, score) in scored:
        sent_words = len(sent.split())
        if total_words + sent_words <= target_words or len(selected) < 2:
            selected.append((orig_idx, sent))
            total_words += sent_words
        if total_words >= target_words:
            break

    selected.sort(key=lambda x: x[0])
    compressed = " ".join([sent for _, sent in selected])
    return {"text": compressed, "word_count": len(compressed.split())}


# =====================================================================
# Main compression function -- the public API
# =====================================================================
def compress_chunks(chunks: list, query: str, target_words: int = 1200) -> dict:
    """
    Two-stage compression: Cross-Encoder pruning + LLMLingua-2.

    This is the MAIN function -- call this from the pipeline.

    Args:
        chunks: List of relevant chunk strings (from retriever).
        query: The user's question.
        target_words: Desired output size (default 1200 words = ~2-3 pages).
                      Stage 1 fills up to this budget; Stage 2 only runs
                      if the text is still over budget.

    Returns:
        dict with all compression stats and the compressed text.
    """
    print(f"\n{'=' * 60}")
    print(f"  TWO-STAGE CONTEXT COMPRESSION")
    print(f"{'=' * 60}")

    context = "\n\n".join(chunks)
    original_words = len(context.split())
    print(f"  Input: {len(chunks)} chunks, {original_words:,} words")
    print(f"  Query: {query}")
    print(f"  Target output: ~{target_words:,} words")

    provence_used = False
    llmlingua2_used = False
    fallback_used = False

    # ---- STAGE 1: Cross-encoder sentence pruning --------------------
    stage1_text = context
    stage1_words = original_words

    if _check_cross_encoder():
        print(f"\n  STAGE 1: Cross-encoder sentence pruning...")
        sentences = _split_into_sentences(context)
        print(f"    Input sentences: {len(sentences)}")

        stage1_result = _stage1_cross_encoder(sentences, query, target_words)
        if stage1_result is not None:
            stage1_text = stage1_result["text"]
            stage1_words = stage1_result["word_count"]
            provence_used = True  # keep key name for API compatibility
            pruned_pct = round((1 - stage1_words / max(original_words, 1)) * 100, 1)
            print(f"    Kept: {stage1_result['sentences_kept']} sentences")
            print(f"    Pruned: {stage1_result['sentences_pruned']} sentences")
            print(f"    Stage 1: {original_words:,} -> {stage1_words:,} words "
                  f"({pruned_pct}% pruned)")
        else:
            print(f"    [Stage 1 skipped -- using full text]")
    else:
        print(f"\n  STAGE 1: Cross-encoder not available -- skipping")

    # ---- STAGE 2: LLMLingua-2 token compression ---------------------
    # WHY only when over budget: token-level compression removes words
    # inside sentences. If Stage 1 already fits the budget, full
    # sentences are more readable and keep every detail (names, numbers).
    compressed_text = stage1_text
    stage2_words = stage1_words
    over_budget = stage1_words > int(target_words * 1.25)

    if not over_budget:
        print(f"\n  STAGE 2: skipped -- {stage1_words:,} words already within "
              f"the ~{target_words:,} word budget (full sentences kept)")
    elif _check_llmlingua2():
        print(f"\n  STAGE 2: LLMLingua-2 token-level compression...")
        stage2_result = _stage2_llmlingua2(stage1_text, query, target_words)
        if stage2_result is not None and stage2_result["word_count"] >= stage1_words:
            print(f"    Stage 2 gave no reduction ({stage1_words} -> "
                  f"{stage2_result['word_count']} words) -- keeping Stage 1 text")
            llmlingua2_used = True
        elif stage2_result is not None:
            stage2_text = stage2_result["text"]
            stage2_count = stage2_result["word_count"]
            kept_ratio = stage2_count / max(stage1_words, 1)
            orig_digits = set(re.findall(r"\d{2,}", stage1_text))
            kept_digits = set(re.findall(r"\d{2,}", stage2_text))
            lost_facts = orig_digits - kept_digits
            # Completeness gate: reject Stage 2 if it ate too much
            # text or dropped numbers/IDs that Stage 1 still had.
            if kept_ratio < 0.75 or (orig_digits and len(lost_facts) > max(2, len(orig_digits) * 0.2)):
                print(f"    Stage 2 dropped too much detail "
                      f"({stage1_words} -> {stage2_count} words, "
                      f"{len(lost_facts)} numbers lost) -- keeping Stage 1 text")
                llmlingua2_used = False
            else:
                compressed_text = stage2_text
                stage2_words = stage2_count
                llmlingua2_used = True
                comp_pct = round((1 - kept_ratio) * 100, 1)
                print(f"    Stage 2: {stage1_words:,} -> {stage2_words:,} words "
                      f"({comp_pct}% compressed)")
        else:
            print(f"    [LLMLingua-2 failed -- trying fallback]")
    else:
        print(f"\n  STAGE 2: LLMLingua-2 not available")

    # ---- FALLBACK: over budget and LLMLingua-2 could not help -------
    # Keep Stage 1 sentences instead of TF-IDF extractive cutting.
    # TF-IDF "summaries" were the main source of missing details.
    if over_budget and not llmlingua2_used:
        print(f"\n  FALLBACK: keeping Stage 1 sentences "
              f"({stage1_words:,} words) — extractive trim skipped "
              f"to preserve complete details")
        compressed_text = stage1_text
        stage2_words = stage1_words
        fallback_used = False

    # ---- Build result -----------------------------------------------
    total_ratio = round(1 - (stage2_words / max(original_words, 1)), 4)

    methods = []
    if provence_used:
        methods.append("CrossEncoder")
    if llmlingua2_used:
        methods.append("LLMLingua-2")
    if fallback_used:
        methods.append("TF-IDF-fallback")
    method_detail = " + ".join(methods) if methods else "none"

    result = {
        "compressed_text": compressed_text,
        "stage1_words_after_provence": stage1_words,
        "stage2_words_after_llmlingua2": stage2_words,
        "original_words": original_words,
        "total_compression_ratio": total_ratio,
        "provence_used": provence_used,
        "llmlingua2_used": llmlingua2_used,
        "fallback_used": fallback_used,
        "method_detail": method_detail,
    }

    # Print summary
    print(f"\n  {'=' * 50}")
    print(f"  COMPRESSION SUMMARY")
    print(f"  {'=' * 50}")
    if provence_used:
        print(f"  Stage 1 CrossEncoder: {original_words:,} -> "
              f"{stage1_words:,} words")
    if llmlingua2_used:
        print(f"  Stage 2 LLMLingua-2:  {stage1_words:,} -> "
              f"{stage2_words:,} words")
    if fallback_used:
        print(f"  Fallback TF-IDF:      {stage1_words:,} -> "
              f"{stage2_words:,} words")
    print(f"  Total: {original_words:,} -> {stage2_words:,} words "
          f"({total_ratio * 100:.1f}% reduction)")
    print(f"  Method: {method_detail}")
    print(f"{'=' * 60}\n")

    return result


# -- CLI entry point ---------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="COF-RAG Compressor -- two-stage CrossEncoder + LLMLingua-2"
    )
    parser.add_argument("--file", required=True, help="Path to PDF or text file")
    parser.add_argument("--query", required=True, help="Query for compression")
    args = parser.parse_args()

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from core.extractor import extract_text
    from core.chunker import chunk_text
    from core.retriever import retrieve_relevant

    if args.file.lower().endswith(".pdf"):
        extraction = extract_text(args.file, "digital_pdf")
    else:
        extraction = extract_text(args.file, "text_file")

    chunking = chunk_text(extraction["text"], strategy="semantic")
    retrieval = retrieve_relevant(chunking["chunks"], args.query, top_k=5)

    try:
        result = compress_chunks(retrieval["relevant_chunks"], args.query)
        print("\n--- COMPRESSED TEXT ---")
        print(result["compressed_text"][:500])
        print(f"\n--- End ({result['stage2_words_after_llmlingua2']} words, "
              f"{result['method_detail']}) ---")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
