"""
file_detector.py -- Universal Input Type Detection Module
==========================================================
Detects the type of ANY input -- file path OR direct text paste.

Supports:
  - digital_pdf:  PDF with extractable text
  - scanned_pdf:  PDF with images of text (needs OCR)
  - image:        JPEG, PNG, WEBP files (needs OCR)
  - text_file:    Plain text / UTF-8 readable files
  - direct_text:  Raw text string pasted directly (no file)

Detection uses magic bytes (file headers) for files, NOT extensions.
This prevents misidentified files from crashing the pipeline.

Usage:
  # File input:
  python file_detector.py --file "path/to/any/file"
  # Direct text:
  python file_detector.py --text "paste your text here"

Dependencies:
  pip install PyMuPDF
"""

import argparse
import os
import sys


# -- Magic byte signatures for file type detection ---------------------
# Every PDF starts with %PDF, every JPEG with FF D8 FF, etc.
MAGIC_BYTES = {
    "pdf":  b"%PDF",
    "jpeg": b"\xff\xd8\xff",
    "png":  b"\x89PNG\r\n\x1a\n",
    "webp_riff": b"RIFF",
    "webp_marker": b"WEBP",
}

# Minimum characters per PDF page to count as "has real text"
MIN_TEXT_CHARS_PER_PAGE = 50


def _detect_by_magic_bytes(file_path: str) -> str:
    """
    Read first 12 bytes of a file to determine its true format.
    Returns: "pdf", "jpeg", "png", "webp", or "unknown"
    """
    try:
        with open(file_path, "rb") as f:
            header = f.read(12)
    except IOError as e:
        raise IOError(f"Cannot read file header: {e}")

    if len(header) < 4:
        return "unknown"

    if header[:4] == MAGIC_BYTES["pdf"]:
        return "pdf"
    elif header[:3] == MAGIC_BYTES["jpeg"]:
        return "jpeg"
    elif header[:8] == MAGIC_BYTES["png"]:
        return "png"
    elif (header[:4] == MAGIC_BYTES["webp_riff"] and
          header[8:12] == MAGIC_BYTES["webp_marker"]):
        return "webp"
    else:
        return "unknown"


def _is_text_file(file_path: str) -> bool:
    """
    Check if a file contains valid UTF-8 text by sampling first 8KB.
    Returns True if over 85% of characters are printable.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            sample = f.read(8192)
        if not sample:
            return False
        printable_ratio = sum(
            1 for c in sample if c.isprintable() or c in "\n\r\t"
        ) / len(sample)
        return printable_ratio > 0.85
    except (UnicodeDecodeError, IOError):
        return False


def _analyze_pdf_pages(file_path: str) -> dict:
    """
    Open a PDF and check each page for extractable text vs images.
    Returns page-by-page analysis for digital vs scanned detection.
    """
    try:
        import pymupdf
    except ImportError:
        raise ImportError("PyMuPDF not installed. Run: pip install PyMuPDF")

    doc = pymupdf.open(file_path)
    total_pages = len(doc)

    if total_pages == 0:
        doc.close()
        return {"text_pages": 0, "image_pages": 0, "total_pages": 0}

    text_pages = 0
    image_pages = 0

    for page_num in range(total_pages):
        page = doc[page_num]
        raw_text = page.get_text("text").strip()
        char_count = len(raw_text)
        image_list = page.get_images(full=True)

        if char_count >= MIN_TEXT_CHARS_PER_PAGE:
            text_pages += 1
        else:
            image_pages += 1

    doc.close()
    return {
        "text_pages": text_pages,
        "image_pages": image_pages,
        "total_pages": total_pages,
    }


def detect_input_type(input_data: str) -> dict:
    """
    Detect the type of any input -- file path OR direct text.

    This is the MAIN function -- call this from the pipeline.

    Logic:
      1. If input_data is short (< 500 chars) AND a file exists at that path:
         -> Treat as a file path, detect type from magic bytes
      2. If input_data is long OR no file found at that path:
         -> Treat as direct text paste (minimum 10 chars)

    Args:
        input_data: Either a file path string or raw text content.

    Returns:
        dict with keys:
            - input_type: "digital_pdf"|"scanned_pdf"|"image"|"text_file"|"direct_text"
            - source: "file" or "direct"
            - file_path: str or None
            - raw_text: str or None (filled only for direct_text)
            - confidence: float (0.0 to 1.0)
            - pages: int (PDFs only, 0 otherwise)
            - size_kb: float or None
    """
    # -- Check if input_data is a file path --------------------------
    is_file = False
    if len(input_data) < 500 and os.path.exists(input_data):
        is_file = True

    if is_file:
        return _detect_file(input_data)
    else:
        return _detect_direct_text(input_data)


def _detect_file(file_path: str) -> dict:
    """Detect type of a file on disk using magic bytes."""

    file_size_kb = round(os.path.getsize(file_path) / 1024, 1)

    if file_size_kb == 0:
        raise ValueError(f"File is empty (0 bytes): {file_path}")

    magic_type = _detect_by_magic_bytes(file_path)

    if magic_type == "pdf":
        # Determine digital vs scanned
        try:
            analysis = _analyze_pdf_pages(file_path)
            total = analysis["total_pages"]
            text_count = analysis["text_pages"]

            if total == 0:
                input_type = "digital_pdf"
                confidence = 0.5
            else:
                text_ratio = text_count / total
                if text_ratio > 0.8:
                    input_type = "digital_pdf"
                    confidence = round(text_ratio, 2)
                else:
                    input_type = "scanned_pdf"
                    confidence = round(1.0 - text_ratio, 2)

            pages = total
        except Exception as e:
            print(f"  [!] PDF analysis failed: {e}")
            input_type = "digital_pdf"
            confidence = 0.5
            pages = 0

    elif magic_type in ("jpeg", "png", "webp"):
        input_type = "image"
        confidence = 1.0
        pages = 0

    elif magic_type == "unknown":
        if _is_text_file(file_path):
            input_type = "text_file"
            confidence = 0.95
            pages = 0
        else:
            raise ValueError(
                f"Unsupported file type: {file_path}\n"
                f"Supported: PDF, JPEG, PNG, WEBP, TXT"
            )
    else:
        raise ValueError(f"Unknown format: {magic_type}")

    result = {
        "input_type": input_type,
        "source": "file",
        "file_path": os.path.abspath(file_path),
        "raw_text": None,
        "confidence": confidence,
        "pages": pages,
        "size_kb": file_size_kb,
    }

    _print_summary(result)
    return result


def _detect_direct_text(text: str) -> dict:
    """Detect and validate direct text input (no file)."""

    clean_text = text.strip()

    if len(clean_text) < 10:
        raise ValueError(
            f"Text too short ({len(clean_text)} chars). "
            f"Minimum 10 characters required."
        )

    result = {
        "input_type": "direct_text",
        "source": "direct",
        "file_path": None,
        "raw_text": clean_text,
        "confidence": 1.0,
        "pages": 0,
        "size_kb": round(len(clean_text.encode("utf-8")) / 1024, 1),
    }

    _print_summary(result)
    return result


def _print_summary(result: dict):
    """Print a clear detection summary to terminal."""

    type_labels = {
        "digital_pdf": "[PDF] DIGITAL PDF (extractable text)",
        "scanned_pdf": "[SCAN] SCANNED PDF (needs OCR)",
        "image":       "[IMG] IMAGE FILE (needs OCR)",
        "text_file":   "[TXT] TEXT FILE (direct read)",
        "direct_text": "[TEXT] DIRECT TEXT INPUT (no file)",
    }

    label = type_labels.get(result["input_type"], result["input_type"])

    print("\n" + "=" * 60)
    print("  INPUT TYPE DETECTION")
    print("=" * 60)

    if result["source"] == "file":
        print(f"  File:       {os.path.basename(result['file_path'])}")
    else:
        word_count = len(result["raw_text"].split())
        preview = result["raw_text"][:80]
        print(f"  Input:      Direct text ({word_count} words)")
        print(f"  Preview:    {preview}...")

    print(f"  Type:       {label}")
    print(f"  Confidence: {result['confidence'] * 100:.0f}%")
    print(f"  Size:       {result['size_kb']} KB")
    if result["pages"] > 0:
        print(f"  Pages:      {result['pages']}")
    print("=" * 60 + "\n")


# -- CLI entry point --------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="COF-RAG Input Detector -- identifies file type or accepts direct text"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to a file to analyze")
    group.add_argument("--text", help="Direct text input string")
    args = parser.parse_args()

    try:
        if args.file:
            result = detect_input_type(args.file)
        else:
            result = detect_input_type(args.text)

        print(f"Result: {result['input_type']} "
              f"(source: {result['source']}, "
              f"confidence: {result['confidence'] * 100:.0f}%)")
    except (FileNotFoundError, ValueError, IOError) as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
