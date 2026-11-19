"""
reranker.py -- Primacy-Recency Reranking Module
=================================================
Reorders compressed sentences using a 4-factor scoring system,
then applies primacy-recency ordering for optimal LLM attention.

Four scoring factors:
  1. TF-IDF relevance to query (weight 0.40):
     How similar each sentence is to the user's question.

  2. Named Entity density (weight 0.25):
     Sentences with names, dates, orgs, money are more informative.

  3. Position score (weight 0.20):
     First 20% of text scores 1.0 (introduction/abstract).
     Last 20% scores 0.9 (conclusions).
     Middle 60% scores 0.5 (less critical details).

  4. Informativeness (weight 0.15):
     Ratio of content words (non-stopwords) to total words.
     Higher = more dense with information.

Primacy-recency ordering:
  Research shows LLMs pay most attention to the FIRST and LAST
  parts of their context window ("Lost in the Middle" paper).
  So we place the highest-scored sentence FIRST (primacy anchor)
  and the second-highest LAST (recency anchor), filling the
  middle with the rest in score order.

Usage:
  python -m core.reranker --text "compressed text" --query "question"

Dependencies:
  pip install spacy scikit-learn
  python -m spacy download en_core_web_sm
"""

import argparse
import os
import re
import sys
import string

# Lazy-loaded spaCy
_nlp = None


def _get_nlp():
    """Lazy-load spaCy model for sentence splitting and NER."""
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("en_core_web_sm")
        except Exception:
            _nlp = None
    return _nlp


def _split_sentences(text: str) -> list:
    """Split text into sentences using spaCy, fallback to regex."""
    nlp = _get_nlp()
    if nlp is not None:
        try:
            doc = nlp(text[:nlp.max_length])
            sents = [s.text.strip() for s in doc.sents
                     if s.text.strip() and len(s.text.strip()) > 5]
            if sents:
                return sents
        except Exception:
            pass

    sents = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sents if s.strip() and len(s.strip()) > 5]


# =====================================================================
# Factor 1: TF-IDF Relevance (weight 0.40)
# =====================================================================
def _score_tfidf(sentences: list, query: str) -> list:
    """
    Score each sentence by TF-IDF cosine similarity to the query.
    Returns list of floats (0.0 to 1.0).
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        return [0.5] * len(sentences)

    all_texts = sentences + [query]
    vectorizer = TfidfVectorizer(stop_words="english")

    try:
        tfidf_matrix = vectorizer.fit_transform(all_texts)
    except ValueError:
        return [0.5] * len(sentences)

    query_vec = tfidf_matrix[-1]
    sent_vecs = tfidf_matrix[:-1]
    scores = cosine_similarity(query_vec, sent_vecs)[0]

    return [round(float(s), 4) for s in scores]


# =====================================================================
# Factor 2: Named Entity Density (weight 0.25)
# =====================================================================
def _score_ner(sentences: list) -> list:
    """
    Score each sentence by named entity density.
    Entities: PERSON, DATE, MONEY, ORG, GPE, LAW, PRODUCT, EVENT.
    Score = entity_count / max(word_count, 1), capped at 1.0.
    """
    nlp = _get_nlp()
    if nlp is None:
        return [0.0] * len(sentences)

    # Important entity types for information density
    important_types = {"PERSON", "DATE", "MONEY", "ORG", "GPE",
                       "LAW", "PRODUCT", "EVENT", "CARDINAL", "PERCENT"}

    scores = []
    for sent in sentences:
        try:
            doc = nlp(sent)
            entity_count = sum(
                1 for ent in doc.ents if ent.label_ in important_types
            )
            word_count = max(len(sent.split()), 1)
            # Normalize: 1 entity per 5 words = score 1.0
            score = min(entity_count / (word_count / 5), 1.0)
            scores.append(round(score, 4))
        except Exception:
            scores.append(0.0)

    return scores


# =====================================================================
# Factor 3: Position Score (weight 0.20)
# =====================================================================
def _score_position(sentences: list) -> list:
    """
    Score by original position in text.
    First 20% = 1.0 (intro/abstract -- highest info density)
    Last 20% = 0.9 (conclusions -- summary of findings)
    Middle 60% = 0.5 (methodology/details -- less critical)

    Why this scoring?
      Research papers front-load key findings in abstract/intro
      and summarize in conclusions. The middle contains details
      that are important but less critical for quick answers.
    """
    n = len(sentences)
    if n == 0:
        return []

    scores = []
    first_boundary = max(1, int(n * 0.2))
    last_boundary = max(first_boundary + 1, int(n * 0.8))

    for i in range(n):
        if i < first_boundary:
            scores.append(1.0)
        elif i >= last_boundary:
            scores.append(0.9)
        else:
            scores.append(0.5)

    return scores


# =====================================================================
# Factor 4: Informativeness (weight 0.15)
# =====================================================================
def _score_informativeness(sentences: list) -> list:
    """
    Score by content word density (non-stopwords / total words).
    Higher ratio = more information-dense sentence.

    Stopwords like "the", "is", "and" carry little meaning.
    Sentences with higher content word ratios pack more information.
    """
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "shall", "can",
        "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after", "above",
        "below", "between", "out", "off", "over", "under", "again",
        "further", "then", "once", "here", "there", "when", "where",
        "why", "how", "all", "both", "each", "few", "more", "most",
        "other", "some", "such", "no", "not", "only", "own", "same",
        "so", "than", "too", "very", "just", "or", "and", "but", "if",
        "while", "that", "this", "these", "those", "it", "its", "he",
        "she", "they", "we", "you", "i", "me", "him", "her", "us",
        "them", "my", "your", "his", "our", "their", "what", "which",
        "who", "whom",
    }

    scores = []
    for sent in sentences:
        words = sent.lower().split()
        words = [w.strip(string.punctuation) for w in words]
        words = [w for w in words if w]

        if not words:
            scores.append(0.0)
            continue

        content_words = sum(1 for w in words if w not in stopwords)
        ratio = content_words / len(words)
        scores.append(round(ratio, 4))

    return scores


# =====================================================================
# Primacy-Recency Ordering
# =====================================================================
def _primacy_recency_order(scored_sentences: list) -> list:
    """
    Reorder sentences for optimal LLM attention.

    From "Lost in the Middle" (Liu et al., 2023):
      LLMs attend most to the FIRST and LAST items in context.
      Information in the middle gets less attention.

    Strategy:
      Position 0 (FIRST):  highest scored sentence  -> primacy anchor
      Position -1 (LAST):  second highest scored     -> recency anchor
      Positions 1..n-2:    remaining in ORIGINAL document order
                           (WHY: long contexts must read coherently;
                           shuffling by score breaks the narrative)
    """
    if len(scored_sentences) <= 2:
        return scored_sentences

    # Sort by score descending
    ranked = sorted(scored_sentences, key=lambda x: x["final_score"], reverse=True)

    # Build primacy-recency ordered list
    ordered = []
    ordered.append(ranked[0])       # Best -> first position (primacy)

    # Middle positions: rest in original document order
    middle = sorted(ranked[2:], key=lambda x: x.get("index", 0))
    ordered.extend(middle)

    ordered.append(ranked[1])       # Second best -> last position (recency)

    # Assign final rank
    for i, item in enumerate(ordered):
        item["rank"] = i + 1

    return ordered


# =====================================================================
# Main reranking function -- the public API
# =====================================================================
def rerank(compressed_text: str, query: str) -> dict:
    """
    Rerank compressed text using 4-factor scoring + primacy-recency.

    This is the MAIN function -- call this from the pipeline.

    Args:
        compressed_text: The compressed context (from compressor).
        query: The user's question.

    Returns:
        dict with keys:
            - final_context: str
            - sentence_count: int
            - top_sentence: str
            - anchor_first: str
            - anchor_last: str
            - scoring_breakdown: list[dict]
    """
    print(f"\n{'=' * 60}")
    print(f"  PRIMACY-RECENCY RERANKING")
    print(f"{'=' * 60}")
    print(f"  Query: {query}")

    sentences = _split_sentences(compressed_text)

    # Deduplicate only. Do NOT drop short sentences: titles, KEY: value
    # lines, and numeric facts are often under 20 characters and were
    # being thrown away before the user ever saw them.
    seen = set()
    unique_sentences = []
    for sent in sentences:
        normalized = re.sub(r'\s+', ' ', sent.strip().lower())
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique_sentences.append(sent)
    sentences = unique_sentences

    # Structured / fact-heavy text must stay in document order.
    # Primacy-recency shuffling splits records, tables, and lists.
    colon_lines = sum(1 for s in sentences if ":" in s)
    digit_lines = sum(1 for s in sentences if re.search(r"\d", s))
    keep_document_order = (
        colon_lines >= max(3, len(sentences) * 0.25)
        or digit_lines >= max(3, len(sentences) * 0.35)
    )

    print(f"  Sentences to rerank: {len(sentences)}")

    if len(sentences) == 0:
        return {
            "final_context": compressed_text,
            "sentence_count": 0,
            "top_sentence": "",
            "anchor_first": "",
            "anchor_last": "",
            "scoring_breakdown": [],
        }

    if len(sentences) == 1:
        return {
            "final_context": sentences[0],
            "sentence_count": 1,
            "top_sentence": sentences[0],
            "anchor_first": sentences[0],
            "anchor_last": sentences[0],
            "scoring_breakdown": [{
                "sentence": sentences[0],
                "tfidf_score": 1.0, "ner_score": 0.0,
                "position_score": 1.0, "info_score": 0.5,
                "final_score": 0.7, "rank": 1,
            }],
        }

    # -- Score all four factors ------------------------------------
    print(f"  Scoring Factor 1: TF-IDF relevance...")
    tfidf_scores = _score_tfidf(sentences, query)

    print(f"  Scoring Factor 2: Named entity density...")
    ner_scores = _score_ner(sentences)

    print(f"  Scoring Factor 3: Position...")
    pos_scores = _score_position(sentences)

    print(f"  Scoring Factor 4: Informativeness...")
    info_scores = _score_informativeness(sentences)

    # -- Combine with weights --------------------------------------
    WEIGHTS = {
        "tfidf": 0.40,
        "ner": 0.25,
        "position": 0.20,
        "info": 0.15,
    }

    scored_sentences = []
    for i, sent in enumerate(sentences):
        final = (
            tfidf_scores[i] * WEIGHTS["tfidf"] +
            ner_scores[i] * WEIGHTS["ner"] +
            pos_scores[i] * WEIGHTS["position"] +
            info_scores[i] * WEIGHTS["info"]
        )
        scored_sentences.append({
            "sentence": sent,
            "index": i,  # original position (keeps middle in document order)
            "tfidf_score": tfidf_scores[i],
            "ner_score": ner_scores[i],
            "position_score": pos_scores[i],
            "info_score": info_scores[i],
            "final_score": round(final, 4),
            "rank": 0,
        })

    # -- Apply primacy-recency ordering ----------------------------
    if keep_document_order:
        print(f"  Keeping document order (structured/fact-heavy context)")
        ordered = sorted(scored_sentences, key=lambda x: x.get("index", 0))
        for i, item in enumerate(ordered):
            item["rank"] = i + 1
    else:
        print(f"  Applying primacy-recency ordering...")
        ordered = _primacy_recency_order(scored_sentences)

    # Build final context as readable paragraphs (~5 sentences each).
    # WHY: a 2-3 page context as one giant line is hard to read/review.
    sents = [item["sentence"] for item in ordered]
    paragraphs = [" ".join(sents[i:i + 5]) for i in range(0, len(sents), 5)]
    final_context = "\n\n".join(paragraphs)

    result = {
        "final_context": final_context,
        "sentence_count": len(ordered),
        "top_sentence": ordered[0]["sentence"] if ordered else "",
        "anchor_first": ordered[0]["sentence"] if ordered else "",
        "anchor_last": ordered[-1]["sentence"] if ordered else "",
        "scoring_breakdown": ordered,
    }

    # Print summary
    print(f"\n  --- Reranking Summary ---")
    print(f"  Sentences reordered: {len(ordered)}")
    print(f"  Score range: {min(s['final_score'] for s in ordered):.4f} "
          f"to {max(s['final_score'] for s in ordered):.4f}")

    print(f"\n  Anchor FIRST (primacy):")
    first_preview = ordered[0]["sentence"][:100]
    print(f"    [{ordered[0]['final_score']:.4f}] {first_preview}...")

    print(f"  Anchor LAST (recency):")
    last_preview = ordered[-1]["sentence"][:100]
    print(f"    [{ordered[-1]['final_score']:.4f}] {last_preview}...")

    print(f"{'=' * 60}\n")

    return result


# -- CLI entry point ---------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="COF-RAG Reranker -- 4-factor primacy-recency reranking"
    )
    parser.add_argument("--text", required=True, help="Text to rerank")
    parser.add_argument("--query", required=True, help="Query for relevance scoring")
    args = parser.parse_args()

    try:
        result = rerank(args.text, args.query)
        print(f"\n--- RERANKED CONTEXT ---")
        print(result["final_context"][:500])
        print(f"\n--- End ({result['sentence_count']} sentences) ---")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
