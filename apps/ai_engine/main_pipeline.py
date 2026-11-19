"""
main_pipeline.py -- COF-RAG Master Pipeline Runner
=====================================================
Runs the FULL pipeline on any input type:
  PDF file -> Image file -> Text file -> Direct text paste

Pipeline sequence:
  Step 1: detect_input_type()   -- identify input
  Step 2: extract_text()        -- get clean text
  Step 3: chunk_text()          -- split into chunks
  Step 4: retrieve_relevant()   -- find relevant chunks
  Step 5: compress_chunks()     -- Provence + LLMLingua-2
  Step 6: rerank()              -- primacy-recency ordering

Usage examples:
  # PDF file:
  python main_pipeline.py --file "paper.pdf" --query "main findings?"

  # Image file:
  python main_pipeline.py --file "scan.jpg" --query "what date?"

  # Text file:
  python main_pipeline.py --file "notes.txt" --query "key points?"

  # Direct text (no file needed):
  python main_pipeline.py --text "paste text here" --query "question?"

  # Interactive mode (type/paste in terminal):
  python main_pipeline.py --interactive
"""

import argparse
import os
import sys
import time

# Add parent directory to path so imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# WHY: the Windows console uses cp1252. PDFs can contain characters it
# cannot show (math symbols like U+1D447). Replace them with "?" when
# printing instead of crashing the whole pipeline.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

from utils.file_detector import detect_input_type
from core.extractor import extract_text
from core.chunker import chunk_text
from core.retriever import retrieve_relevant
from core.compressor import compress_chunks
from core.reranker import rerank
from core.records import (records_from_chunks, merge_records,
                          select_relevant_records, format_records_block,
                          format_records_summary)


def _print_header():
    """Print the pipeline header."""
    print("\n")
    print("+" + "=" * 58 + "+")
    print("|" + " " * 58 + "|")
    print("|" + "      COF-RAG Pipeline Runner".center(58) + "|")
    print("|" + "  Provence + LLMLingua-2 Two-Stage Compression".center(58) + "|")
    print("|" + " " * 58 + "|")
    print("+" + "=" * 58 + "+")
    print()


# Step timings collected during a run (read by the FastAPI server)
_STEP_TIMINGS = []


def _print_step(step_num: int, name: str, elapsed: float, status: str = "OK"):
    """Print a step completion line and remember its timing."""
    _STEP_TIMINGS.append({"step": name, "elapsed_seconds": round(elapsed, 2)})
    check = "[OK]" if status == "OK" else "[!!]"
    print(f"  {check} Step {step_num} -- {name:<30s} {elapsed:.1f}s")


def run_pipeline(input_data: str, query: str, top_k: int = 5,
                 target_words: int = 1200) -> dict:
    """
    Run the full COF-RAG pipeline.

    This is the MAIN function -- the single entry point for everything.

    Args:
        input_data: File path OR raw text string.
        query: The user's question.
        top_k: Minimum number of chunks to retrieve (default 5).
        target_words: Size of the final context (default 1200 words,
                      about 2-3 pages). More words = more complete details.

    Returns:
        dict with all pipeline results and timing.
    """
    pipeline_start = time.time()
    _print_header()

    # Show input info
    if os.path.exists(input_data) and len(input_data) < 500:
        print(f"  Input: {os.path.basename(input_data)}")
    else:
        word_count = len(input_data.split())
        print(f"  Input: Direct text ({word_count} words)")
    print(f"  Query: {query}")
    print()
    print("-" * 60)

    results = {}

    # ── Step 1: Input Detection ──────────────────────────────────────
    t0 = time.time()
    try:
        detection = detect_input_type(input_data)
        results["detection"] = detection
        _print_step(1, "Input Detection", time.time() - t0)
        print(f"         Type: {detection['input_type']}")
    except Exception as e:
        print(f"  [FAIL] Step 1 -- Input Detection: {e}")
        return results

    # ── Step 2: Text Extraction ──────────────────────────────────────
    t0 = time.time()
    try:
        # For direct_text, pass the raw text; for files, pass the path
        if detection["input_type"] == "direct_text":
            extraction = extract_text(detection["raw_text"], "direct_text")
        else:
            extraction = extract_text(
                detection["file_path"], detection["input_type"]
            )
        results["extraction"] = extraction
        _print_step(2, "Text Extraction", time.time() - t0)
        print(f"         Words extracted: {extraction['word_count']:,}")
    except Exception as e:
        print(f"  [FAIL] Step 2 -- Text Extraction: {e}")
        return results

    # ── Step 3: Chunking ─────────────────────────────────────────────
    t0 = time.time()
    try:
        chunking = chunk_text(extraction["text"], strategy="auto")
        results["chunking"] = chunking

        # Records found by the extractor (raw text, exact values) plus any
        # record chunks the chunker detected (fallback for direct text).
        chunk_records, normal_chunks = records_from_chunks(chunking["chunks"])
        normal_ids = [cid for cid, chunk in zip(chunking["chunk_ids"], chunking["chunks"])
                      if chunk in normal_chunks]
        all_records = merge_records(extraction.get("structured_records", []), chunk_records)

        _print_step(3, "Chunking", time.time() - t0)
        print(f"         Chunks: {len(normal_chunks)} text chunks | "
              f"Strategy: {chunking['strategy_used']}")
        if all_records:
            print(f"         Structured records: {len(all_records)} (kept out of chunking)")
    except Exception as e:
        print(f"  [FAIL] Step 3 -- Chunking: {e}")
        return results

    # ── Step 3b: Pick the records this query needs ───────────────────
    # WHY: records are exact data (names, IBANs). They never go through
    # retrieval/compression/reranking, which would scramble them.
    selected_records = select_relevant_records(all_records, query)
    results["structured_records"] = all_records
    results["selected_records"] = selected_records
    if all_records:
        print(f"\n  [RECORDS] {len(selected_records)} of {len(all_records)} records "
              f"match this query (passed through EXACT, no compression)")
        if selected_records:
            for line in format_records_summary(selected_records).split("\n"):
                print(f"            {line}")

    # ── Step 4: Retrieval (narrative text only) ──────────────────────
    t0 = time.time()
    try:
        if normal_chunks:
            retrieval = retrieve_relevant(
                normal_chunks, query, top_k=top_k, chunk_ids=normal_ids,
                target_words=target_words
            )
        else:
            retrieval = {"relevant_chunks": [], "chunk_ids": [], "scores": [],
                         "retrieval_method": "none (no text chunks)"}
        results["retrieval"] = retrieval
        _print_step(4, "Retrieval", time.time() - t0)
        best_score = retrieval["scores"][0] if retrieval["scores"] else 0
        print(f"         Selected: {len(retrieval['relevant_chunks'])} chunks | "
              f"Best score: {best_score:.4f}")
    except Exception as e:
        print(f"  [FAIL] Step 4 -- Retrieval: {e}")
        return results

    # ── Step 5: Two-Stage Compression (narrative text only) ──────────
    t0 = time.time()
    empty_compression = {
        "compressed_text": "",
        "original_words": 0,
        "stage1_words_after_provence": 0,
        "stage2_words_after_llmlingua2": 0,
        "total_compression_ratio": 0.0,
        "provence_used": False,
        "llmlingua2_used": False,
        "fallback_used": False,
        "method_detail": "skipped (no text chunks)",
    }
    try:
        if retrieval["relevant_chunks"]:
            # Put retrieved chunks back in DOCUMENT order before compressing
            # (WHY: the final 2-3 pages should follow the document's flow)
            doc_ordered = [c for _, c in sorted(
                zip(retrieval["chunk_ids"], retrieval["relevant_chunks"]),
                key=lambda pair: pair[0])]
            compression = compress_chunks(doc_ordered, query, target_words=target_words)
        else:
            compression = dict(empty_compression)
        results["compression"] = compression
        _print_step(5, "Two-Stage Compression", time.time() - t0)

        if compression["provence_used"]:
            print(f"         CrossEncoder: {compression['original_words']:,} -> "
                  f"{compression['stage1_words_after_provence']:,} words")
        if compression["llmlingua2_used"]:
            print(f"         LLMLingua-2:  "
                  f"{compression['stage1_words_after_provence']:,} -> "
                  f"{compression['stage2_words_after_llmlingua2']:,} words")
        if compression["fallback_used"]:
            print(f"         Fallback:     "
                  f"{compression['stage1_words_after_provence']:,} -> "
                  f"{compression['stage2_words_after_llmlingua2']:,} words")
        if selected_records:
            print(f"         Records:      {len(selected_records)} kept exact (not compressed)")
        ratio_pct = compression["total_compression_ratio"] * 100
        print(f"         Text reduction: {ratio_pct:.1f}%")
    except Exception as e:
        print(f"  [FAIL] Step 5 -- Compression: {e} -- using retrieved text as-is")
        compression = dict(empty_compression)
        compression["compressed_text"] = "\n\n".join(retrieval["relevant_chunks"])
        compression["fallback_used"] = True
        compression["method_detail"] = "none (compression failed)"
        results["compression"] = compression

    # ── Step 6: Reranking (narrative text only) ──────────────────────
    t0 = time.time()
    try:
        if compression["compressed_text"].strip():
            reranking = rerank(compression["compressed_text"], query)
        else:
            reranking = {"final_context": "", "sentence_count": 0,
                         "top_sentence": "", "anchor_first": "",
                         "anchor_last": "", "scoring_breakdown": []}
        results["reranking"] = reranking
        _print_step(6, "Reranking", time.time() - t0)
        print(f"         Sentences reordered: {reranking['sentence_count']}")
    except Exception as e:
        print(f"  [FAIL] Step 6 -- Reranking: {e}")
        reranking = {"final_context": compression["compressed_text"], "sentence_count": 0}
        results["reranking"] = reranking

    # ── Final Output: exact records FIRST, then relevant text ────────
    total_time = time.time() - pipeline_start
    sections = []
    if selected_records:
        sections.append(format_records_block(selected_records))
    if reranking["final_context"].strip():
        if selected_records:
            sections.append("RELEVANT CONTEXT:\n" + reranking["final_context"].strip())
        else:
            sections.append(reranking["final_context"].strip())
    final_context = "\n\n".join(sections)
    final_words = len(final_context.split())
    record_words = sum(len(r["formatted_text"].split()) for r in all_records)
    original_words = extraction["word_count"] + record_words

    print()
    print("=" * 60)
    print("   FINAL OPTIMIZED CONTEXT")
    print("=" * 60)
    print()
    print(final_context)
    print()
    print("=" * 60)
    print()

    # Pipeline summary
    print("  PIPELINE SUMMARY:")
    print(f"  Input words:     {original_words:,}")
    print(f"  Final words:     {final_words:,}")
    if original_words > 0:
        reduction = (1 - final_words / original_words) * 100
        print(f"  Reduction:       {reduction:.1f}%")
    print(f"  Records (exact): {len(selected_records)} of {len(all_records)}")
    print(f"  CrossEncoder:    {'YES' if compression.get('provence_used') else 'NO'}")
    print(f"  LLMLingua-2:     {'YES' if compression.get('llmlingua2_used') else 'NO'}")
    print(f"  Total time:      {total_time:.1f}s")
    print()
    print(f"  Context is ready to send to any LLM.")
    print()

    results["final_context"] = final_context
    results["final_words"] = final_words
    results["original_words"] = original_words
    results["total_time"] = total_time

    return results


def run_interactive():
    """
    Interactive mode: paste text + ask questions in terminal.
    """
    _print_header()
    print("  INTERACTIVE MODE")
    print("  Paste your text below. Press Enter twice when done:")
    print("-" * 60)

    lines = []
    empty_count = 0
    while True:
        try:
            line = input()
            if line == "":
                empty_count += 1
                if empty_count >= 2:
                    break
                lines.append("")
            else:
                empty_count = 0
                lines.append(line)
        except EOFError:
            break

    text = "\n".join(lines).strip()

    if len(text) < 10:
        print("\n  [ERROR] Text too short. Need at least 10 characters.")
        return

    print(f"\n  Text received: {len(text.split())} words")
    print()

    query = input("  Enter your question: ").strip()
    if not query:
        query = "What are the main points?"
        print(f"  Using default query: {query}")

    print()
    run_pipeline(text, query)


# -- CLI entry point ---------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="COF-RAG Pipeline -- full document processing with "
                    "Provence + LLMLingua-2 two-stage compression"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to PDF, image, or text file")
    group.add_argument("--text", help="Direct text string to process")
    group.add_argument("--interactive", action="store_true",
                       help="Interactive mode: paste text in terminal")

    parser.add_argument("--query", help="Question to optimize context for")
    parser.add_argument("--target-words", type=int, default=1200,
                        help="Final context size in words (default 1200 = ~2-3 pages)")
    parser.add_argument("--top_k", type=int, default=5,
                        help="Number of chunks to retrieve (default 5)")

    args = parser.parse_args()

    if args.interactive:
        run_interactive()
    else:
        input_data = args.file if args.file else args.text
        query = args.query

        if not query:
            print("[ERROR] --query is required when using --file or --text")
            sys.exit(1)

        try:
            results = run_pipeline(input_data, query, top_k=args.top_k,
                                   target_words=args.target_words)
        except Exception as e:
            print(f"\n[FATAL ERROR] {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
